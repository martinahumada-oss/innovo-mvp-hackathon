"""Diseño editorial INNOVO con evidencia y alineación ANID trazable."""
from datetime import datetime
from io import BytesIO
import json
from pathlib import Path
import unicodedata
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from banco_desafios import vigencia, evaluar_trl
from mvp_plan import cambios_pendientes
from anid_tendencias import alineacion_postulante, FUENTE

MORADO = colors.HexColor('#49305f')
MAGENTA = colors.HexColor('#ae1766')
TINTA = colors.HexColor('#302936')
SUAVE = colors.HexColor('#f3eef7')


def generar_plan_pdf(perfil, banco, seguimiento, informe=None):
    if avisos := cambios_pendientes(perfil, banco, seguimiento):
        raise ValueError(' '.join(avisos) + ' Revisa y guarda nuevamente la selección.')
    if informe:
        from informe_mvp import validar_aprobacion
        validar_aprobacion(informe, perfil, banco, seguimiento)
    elif not seguimiento.get('mentor') or not seguimiento.get('responsable'):
        raise ValueError('Guarda primero el contacto y el plan de mentoría.')
    normal, negrita = 'Helvetica', 'Helvetica-Bold'
    for nombre, archivo in [('InnovoRegular', 'arial.ttf'), ('InnovoBold', 'arialbd.ttf')]:
        ruta = Path('C:/Windows/Fonts') / archivo
        if ruta.exists() and nombre not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(nombre, str(ruta)))
    if 'InnovoRegular' in pdfmetrics.getRegisteredFontNames() and 'InnovoBold' in pdfmetrics.getRegisteredFontNames():
        normal, negrita = 'InnovoRegular', 'InnovoBold'
    estilos = {
        'portada': ParagraphStyle('portada', fontName=negrita, fontSize=30, leading=35, textColor=MORADO, spaceAfter=16),
        'subtitulo': ParagraphStyle('subtitulo', fontName=negrita, fontSize=18, leading=23, textColor=MAGENTA, spaceAfter=14),
        'seccion': ParagraphStyle('seccion', fontName=negrita, fontSize=17, leading=22, textColor=MORADO, spaceAfter=12, keepWithNext=True),
        'apartado': ParagraphStyle('apartado', fontName=negrita, fontSize=11, leading=15, textColor=MORADO, spaceBefore=8, spaceAfter=6, keepWithNext=True),
        'cuerpo': ParagraphStyle('cuerpo', fontName=normal, fontSize=10, leading=15, textColor=TINTA, spaceAfter=10),
        'nota': ParagraphStyle('nota', fontName=normal, fontSize=8, leading=11, textColor=colors.HexColor('#6c6273'), spaceAfter=8),
        'celda': ParagraphStyle('celda', fontName=normal, fontSize=9, leading=13, textColor=TINTA),
        'cabecera': ParagraphStyle('cabecera', fontName=negrita, fontSize=8, leading=11, textColor=colors.white),
        'etiqueta': ParagraphStyle('etiqueta', fontName=negrita, fontSize=8, leading=11, textColor=MAGENTA, spaceAfter=8),
    }
    contenido = []
    def limpiar(valor):
        return ''.join(c for c in str(valor if valor not in (None, '') else 'No informado') if unicodedata.category(c) not in ('So', 'Cf'))
    def p(valor, estilo='cuerpo'):
        return Paragraph(escape(limpiar(valor)).replace('\n', '<br/>'), estilos[estilo])
    def texto(valor, estilo='cuerpo'):
        contenido.append(p(valor, estilo))
    def seccion(numero, titulo, nueva=True):
        if nueva:
            contenido.append(PageBreak())
        texto(f'INNOVO / {numero}', 'etiqueta')
        texto(titulo, 'seccion')
    def tabla(cabeceras, filas, anchos):
        t = Table([[p(x, 'cabecera') for x in cabeceras]] + [[p(x, 'celda') for x in f] for f in filas],
                  colWidths=anchos, repeatRows=1, splitInRow=1, hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), MORADO),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [SUAVE, colors.white]),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 10),
            ('RIGHTPADDING', (0, 0), (-1, -1), 10), ('TOPPADDING', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
            ('LINEBELOW', (0, 0), (-1, 0), 2, MAGENTA)]))
        contenido.extend([t, Spacer(1, 12)])
    def panel(titulo, cuerpo):
        t = Table([[p(titulo, 'apartado')], [p(cuerpo)]], colWidths=[499], splitInRow=1)
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), SUAVE), ('LINEBEFORE', (0, 0), (0, -1), 3, MAGENTA),
            ('LEFTPADDING', (0, 0), (-1, -1), 14), ('RIGHTPADDING', (0, 0), (-1, -1), 14),
            ('TOPPADDING', (0, 0), (-1, -1), 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 7)]))
        contenido.extend([t, Spacer(1, 15)])

    logo = Path(__file__).parent / 'logo_innovo.png'
    if logo.exists():
        img = Image(str(logo))
        img.drawWidth, img.drawHeight = 135, 135 * img.imageHeight / img.imageWidth
        img.hAlign = 'LEFT'
        contenido.extend([img, Spacer(1, 28)])
    texto('GESTIÓN DE OPORTUNIDADES · INNOVO USACH', 'etiqueta')
    texto('Informe estratégico\nde oportunidades' if informe else 'Plan de desafíos\ny mentoría', 'portada')
    texto(perfil['nombre'], 'subtitulo')
    responsable = informe['revisor'] if informe else seguimiento['responsable']
    tabla(['FECHA', 'RESPONSABLE', 'ESTADO'], [[datetime.now().strftime('%d-%m-%Y'), responsable,
          'Aprobado por el gestor' if informe else 'Plan del gestor']], [110, 224, 165])
    if perfil.get('tipo_registro') == 'FICTICIO_DEMOSTRACION':
        panel('FICTICIO · DEMOSTRACIÓN', 'Las cifras, validaciones y actividades del postulante son simuladas. Los registros del banco y ANID corresponden a sus respectivas fuentes documentales.')
    if informe:
        texto('Síntesis ejecutiva', 'seccion')
        texto(informe['contenido']['sintesis'])
    else:
        texto('Objetivo del plan', 'seccion')
        texto(seguimiento['justificacion'])
    texto('CONTENIDO', 'etiqueta')
    texto('01 Perfil y diagnóstico   /   02 Desafíos seleccionados\n03 Alineación histórica ANID   /   04 Mentoría y hoja de ruta', 'nota')
    if informe:
        texto(f"Aprobación: {informe['fecha']} · {informe['procedencia']}", 'nota')

    seccion('01', 'Perfil y diagnóstico')
    tabla(['DIMENSIÓN', 'INFORMACIÓN DECLARADA'], [[label, perfil.get(key) or 'Pendiente'] for label, key in [
        ('Solución', 'descripcion_solucion'), ('Problema', 'problema_resuelve'), ('Tecnología', 'tecnologia_descripcion'),
        ('Estado comercial', 'estado_comercial'), ('TRL declarado', 'trl_declarado'), ('TRL objetivo (meta)', 'trl_objetivo'),
        ('Validación declarada', 'validacion_tecnica_declarada')]], [124, 375])
    if informe:
        for titulo, campo in [('Problema y oportunidad', 'necesidad'), ('Foco recomendado', 'foco'), ('Brechas y riesgos', 'brechas')]:
            texto(titulo, 'apartado')
            texto(informe['contenido'][campo])

    seccion('02', 'Desafíos seleccionados')
    texto('Selección manual del gestor. Requiere confirmar vigencia, requisitos y disponibilidad de la contraparte.', 'nota')
    panel('Fundamento de la selección', seguimiento['justificacion'])
    por_id = banco.set_index('id', drop=False)
    ids = seguimiento.get('desafios', [])
    if not ids:
        texto('No se identificó un desafío adecuado. La mentoría ayudará a precisar el foco de exploración.')
    else:
        tabla(['REGISTRO', 'SECTOR', 'VIGENCIA'], [[i + '\n' + por_id.loc[i, 'titulo'], por_id.loc[i, 'industria'],
              vigencia(por_id.loc[i])] for i in ids], [248, 141, 110])
    for numero, identificador in enumerate(ids, 1):
        r = por_id.loc[identificador]
        seccion(f'02.{numero:02d} / {identificador}', r['titulo'])
        texto(r['problema'])
        tabla(['CONTEXTO', 'EVIDENCIA DEL BANCO'], [
            ('Tipo', r['tipo_registro']), ('Responsable', r['nombre_empresa'] or 'Pendiente de atribución'),
            ('Atribución', r['atribucion']), ('Vigencia', vigencia(r) + ' · ' + r['estado_documentado']),
            ('Requisitos', r['requisitos']), ('Revisión TRL', evaluar_trl(r['requisitos'], perfil.get('trl_declarado', ''))[1])], [124, 375])
        if informe:
            d = next(d for d in informe['contenido']['desafios'] if d['id'] == identificador)
            for titulo, campo in [('Aplicación propuesta', 'aplicacion'), ('Condiciones por validar', 'validacion')]:
                texto(titulo, 'apartado')
                texto(d[campo])
            panel('Próxima acción', d['accion'])
        texto(f"Fuente: {r['fuente_principal']}\nRevisión: {r['fecha_revision']} · Calidad: {r['calidad_evidencia']}", 'nota')

    seccion('03', 'Alineación histórica con ANID')
    filas = informe.get('alineacion_anid', []) if informe else alineacion_postulante(perfil, banco, seguimiento)
    texto('La tecnología del postulante se contrasta con los sectores seleccionados en el histórico de proyectos adjudicados. Sin selección se usa su industria declarada.')
    disponibles = [f for f in filas if f['estado_anid'] == 'Disponible']
    if disponibles:
        tabla(['SECTOR', 'ALINEACIÓN /100', 'PROYECTOS', 'PERÍODO / TENDENCIA'],
              [[f['sector'], f"{f['score_anid']:g}", f['proyectos_anid_recientes'], f"{f['periodo_anid']}\n{f['tendencia_anid']}"] for f in disponibles],
              [175, 85, 72, 167])
        for f in disponibles:
            texto(f['sector'], 'apartado')
            texto(f"{f['periodo_anid']}: {f['proyectos_anid_recientes']} de {f['universo_anid_reciente']} proyectos del universo reciente. "
                  f"{f['periodo_anid_anterior']}: {f['proyectos_anid_anteriores']} de {f['universo_anid_anterior']}. "
                  f"Cuota: {f['cuota_anid_anterior']}% → {f['cuota_anid_reciente']}%.", 'nota')
            ejemplos = json.loads(f['ejemplos_anid'])
            if ejemplos:
                tabla(['PROYECTO / AÑO', 'TÍTULO SEGÚN ANID'], [[f"{e['codigo']}\n{e['anio']}", e['titulo']] for e in ejemplos], [124, 375])
            else:
                texto('Sin proyectos coincidentes en el período reciente.', 'nota')
    else:
        panel('ANID no disponible', 'La base histórica está ausente o no tiene el esquema esperado. No se sustituye la ausencia por un valor cero.')
    panel('Cómo interpretar esta señal', '20 × log2(1 + proyectos recientes), máximo 100. La tendencia compara cuotas en dos ventanas de cinco años. '
          'Es una señal léxica exploratoria; no acredita fondos abiertos, elegibilidad, demanda ni probabilidad de éxito. No modifica la selección de desafíos.')
    texto('Fuente: ' + FUENTE + '\nCorte de la base local: 2025. No se actualiza desde Internet al generar el informe.', 'nota')

    seccion('04', 'Mentoría y próximos pasos')
    mentor = seguimiento.get('mentor')
    if mentor:
        tabla(['MENTORÍA INNOVO', 'CONTACTO Y SEGUIMIENTO'], [
            ('Mentor', mentor['Nombre completo']), ('Categoría', mentor.get('Categoría Mentor', '')),
            ('Correo', mentor.get('Correo Electrónico') or 'No registrado'), ('LinkedIn', mentor.get('Perfil de LinkedIn') or 'No registrado'),
            ('Estado informado', seguimiento['estado_contacto'])], [124, 375])
    else:
        panel('Mentor por seleccionar', 'Consultar el directorio INNOVO USACH y confirmar disponibilidad para revisar oportunidades y brechas.')
    texto('El estado del contacto lo informa el gestor. El sistema no envía correos ni verifica reuniones.', 'nota')
    panel('Próximo compromiso', seguimiento.get('proxima_accion') or 'Seleccionar un mentor y acordar próximos pasos con el postulante.')
    if informe:
        texto('Hoja de ruta de 90 días', 'seccion')
        tabla(['HORIZONTE', 'ACCIÓN, ENTREGABLE Y CONDICIÓN DE AVANCE'], [
            ('Días 0-30\nValidar', informe['contenido']['dias_0_30']),
            ('Días 31-60\nPreparar', informe['contenido']['dias_31_60']),
            ('Días 61-90\nDecidir', informe['contenido']['dias_61_90'])], [100, 399])
    texto('Fuentes y alcance', 'apartado')
    texto('Perfil y formulario declarado del postulante; banco de desafíos, histórico ANID y directorio de mentores. Las referencias y declaraciones no sustituyen una validación técnica o comercial ni la revisión de bases vigentes.', 'nota')
    salida = BytesIO()
    def marco(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(MORADO)
        canvas.rect(0, A4[1]-12, A4[0], 12, fill=1, stroke=0)
        canvas.setFillColor(MAGENTA)
        canvas.rect(0, A4[1]-12, 150, 12, fill=1, stroke=0)
        if doc.page > 1:
            canvas.setFont(negrita, 8)
            canvas.setFillColor(MORADO)
            canvas.drawString(48, A4[1]-36, 'INNOVO USACH / INFORME ESTRATÉGICO')
        canvas.setStrokeColor(MAGENTA)
        canvas.line(48, 40, 547, 40)
        canvas.setFont(normal, 8)
        canvas.setFillColor(TINTA)
        canvas.drawString(48, 26, 'INNOVO USACH · ' + ('Revisado por el gestor' if informe else 'Plan del gestor'))
        canvas.drawRightString(547, 26, f'{doc.page:02d}')
        canvas.restoreState()
    SimpleDocTemplate(salida, pagesize=A4, leftMargin=48, rightMargin=48, topMargin=58, bottomMargin=58,
                      title='Informe estratégico - ' + perfil['nombre'], author='INNOVO USACH').build(contenido, onFirstPage=marco, onLaterPages=marco)
    return salida.getvalue()
