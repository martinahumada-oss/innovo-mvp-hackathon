"""Perfil canónico de postulantes del MVP."""
import re
import pandas as pd

CAMPOS = '''id id_empresa_postulante id_postulacion_vigente nombre industria_principal_declarada
industria_principal_id descripcion_solucion problema_resuelve usuario_objetivo decisor_compra pagador
beneficio_declarado diferenciacion_declarada modelo_ingresos_actual modelo_ingresos_proyectado
canal_venta_declarado tecnologia_descripcion integracion_tecnologica capacidades_declaradas
capacidades_proyectadas casos_uso_declarados activos_contextos_declarados trl_declarado trl_objetivo
validacion_tecnica_declarada beneficios_medidos_declarados beneficios_por_medir
antiguedad_tecnologia_categoria estado_patente titularidad_pi_declarada proteccion_adicional
estado_comercial evidencia_comercial_declarada ingresos_solucion_12m moneda_ingresos fecha_corte_ingresos
concentracion_cliente_categoria clientes_activos_cantidad pilotos_cantidad_categoria
pilotos_convertidos_cantidad pipeline_declarado moneda_pipeline ticket_declarado moneda_ticket
margen_bruto_declarado_pct necesidad_financiamiento moneda_financiamiento horizonte_financiamiento_meses
capacidad_comercial_declarada objetivo_comercial_6m brechas_equipo_declaradas
industrias_explorables_declaradas 
version_perfil actualizado_en origen_perfil estado_revision tipo_registro'''.split()

def trl_numero(valor):
    m = re.fullmatch(r'(?:TRL\s*)?([1-9])(?:\s*:\s*[^\n]+)?', str(valor).strip(), re.I)
    return int(m[1]) if m else None


def validar_perfiles(df):
    for campo in ('trl_declarado', 'trl_objetivo'):
        if campo in df and any(v and trl_numero(v) is None for v in df[campo]):
            raise ValueError(f'{campo}: usa un entero de 1 a 9 o deja vacío si no se conoce.')
    for campo in ('ingresos_solucion_12m', 'clientes_activos_cantidad', 'pilotos_convertidos_cantidad',
                  'pipeline_declarado', 'ticket_declarado', 'necesidad_financiamiento', 'margen_bruto_declarado_pct'):
        for valor in df.get(campo, []):
            if valor and not re.fullmatch(r'\d+(?:\.\d+)?', valor):
                raise ValueError(f'{campo}: usa un número positivo sin separador de miles, o vacío.')
            if valor and campo.endswith('_cantidad') and not valor.isdigit():
                raise ValueError(f'{campo}: debe ser entero.')
            if valor and campo == 'margen_bruto_declarado_pct' and float(valor) > 100:
                raise ValueError('El margen porcentual debe estar entre 0 y 100.')
