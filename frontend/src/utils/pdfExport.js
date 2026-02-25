import jsPDF from 'jspdf'
import 'jspdf-autotable'

const DIAS_SEMANA = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado']

const PRIMARY = [26, 86, 50]       // #1a5632
const PRIMARY_DARK = [15, 61, 34]  // #0f3d22
const HEADER_BG = [26, 86, 50]
const ROW_ALT = [248, 250, 252]    // #f8fafc
const SUBTOTAL_BG = [226, 232, 240] // #e2e8f0
const TEXT = [30, 41, 59]          // #1e293b
const TEXT_LIGHT = [100, 116, 139] // #64748b

function formatNumber(n) {
  if (n == null) return '-'
  return n.toLocaleString('es-AR')
}

function today() {
  return new Date().toLocaleDateString('es-AR')
}

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

/**
 * Adds a professional header to the PDF document.
 * Returns the Y position after the header.
 */
function addHeader(doc, title, subtitle) {
  const pageWidth = doc.internal.pageSize.getWidth()
  const margin = 20

  // Title bar
  doc.setFillColor(...PRIMARY_DARK)
  doc.rect(0, 0, pageWidth, 28, 'F')

  doc.setTextColor(255, 255, 255)
  doc.setFontSize(16)
  doc.setFont('helvetica', 'bold')
  doc.text('PROYECCIÓN DE FAENA', margin, 12)

  doc.setFontSize(10)
  doc.setFont('helvetica', 'normal')
  doc.text(title, margin, 20)

  // Date on the right
  doc.setFontSize(9)
  doc.text(`Fecha: ${today()}`, pageWidth - margin, 20, { align: 'right' })

  let y = 36

  if (subtitle) {
    doc.setTextColor(...TEXT_LIGHT)
    doc.setFontSize(9)
    doc.text(subtitle, margin, y)
    y += 8
  }

  return y
}

/**
 * Adds page numbers to all pages.
 */
function addPageNumbers(doc) {
  const totalPages = doc.internal.getNumberOfPages()
  for (let i = 1; i <= totalPages; i++) {
    doc.setPage(i)
    const pageWidth = doc.internal.pageSize.getWidth()
    const pageHeight = doc.internal.pageSize.getHeight()
    doc.setFontSize(8)
    doc.setTextColor(...TEXT_LIGHT)
    doc.text(`Página ${i} de ${totalPages}`, pageWidth / 2, pageHeight - 10, { align: 'center' })
  }
}

/**
 * Common autotable styles.
 */
function tableStyles() {
  return {
    headStyles: {
      fillColor: HEADER_BG,
      textColor: [255, 255, 255],
      fontStyle: 'bold',
      fontSize: 8,
      halign: 'center',
      cellPadding: 3,
    },
    bodyStyles: {
      fontSize: 8,
      textColor: TEXT,
      cellPadding: 2.5,
    },
    alternateRowStyles: {
      fillColor: ROW_ALT,
    },
    styles: {
      lineColor: [226, 232, 240],
      lineWidth: 0.3,
      font: 'helvetica',
    },
    margin: { left: 20, right: 20 },
    tableLineColor: [226, 232, 240],
    tableLineWidth: 0.3,
  }
}

// ─────────────────────────────────────────────────
// OFERTA PDF
// ─────────────────────────────────────────────────

export function exportOfertaPDF(oferta) {
  if (!oferta || !oferta.ofertas) return

  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' })
  const pageWidth = doc.internal.pageSize.getWidth()

  let y = addHeader(doc, 'Reporte de Oferta', `Total: ${formatNumber(oferta.total_pollos)} pollos — ${oferta.total_lotes} lotes — ${Object.keys(oferta.granjas || {}).length} granjas`)

  // Stats summary line
  doc.setFontSize(10)
  doc.setFont('helvetica', 'bold')
  doc.setTextColor(...PRIMARY)
  doc.text('Resumen por Granja', 20, y)
  y += 4

  // Farm summary table
  const granjas = oferta.granjas || {}
  const farmRows = Object.entries(granjas)
    .sort((a, b) => b[1].pollos - a[1].pollos)
    .map(([nombre, info]) => [nombre, info.lotes, formatNumber(info.pollos)])

  doc.autoTable({
    startY: y,
    head: [['Granja', 'Lotes', 'Pollos']],
    body: farmRows,
    ...tableStyles(),
    columnStyles: {
      0: { halign: 'left', fontStyle: 'bold' },
      1: { halign: 'center' },
      2: { halign: 'right' },
    },
    tableWidth: Math.min(pageWidth - 40, 160),
    margin: { left: (pageWidth - Math.min(pageWidth - 40, 160)) / 2 },
  })

  y = doc.lastAutoTable.finalY + 10

  // Full offer table
  doc.setFontSize(10)
  doc.setFont('helvetica', 'bold')
  doc.setTextColor(...PRIMARY)
  doc.text(`Oferta Completa (${oferta.ofertas.length} lotes)`, 20, y)
  y += 4

  const ofertaRows = oferta.ofertas.map((o, i) => [
    i + 1,
    o.fecha_peso || '-',
    o.granja,
    o.galpon,
    o.nucleo,
    formatNumber(o.cantidad),
    o.sexo || '-',
    o.edad_proyectada ?? '-',
    o.peso_muestreo_proy?.toFixed(2) ?? '-',
    o.ganancia_diaria?.toFixed(3) ?? '-',
    o.dias_proyectados ?? '-',
    o.edad_real ?? '-',
    o.peso_muestreo_real?.toFixed(2) ?? '-',
    o.fecha_ingreso || '-',
  ])

  doc.autoTable({
    startY: y,
    head: [['#', 'Fecha Peso', 'Granja', 'Galpón', 'Núcleo', 'Cantidad', 'Sexo', 'Edad Proy.', 'Peso Proy.', 'Ganancia', 'Días Proy.', 'Edad Real', 'Peso Real', 'F. Ingreso']],
    body: ofertaRows,
    ...tableStyles(),
    columnStyles: {
      0: { halign: 'center', cellWidth: 8 },
      2: { fontStyle: 'bold', halign: 'left' },
      3: { halign: 'center' },
      4: { halign: 'center' },
      5: { halign: 'right' },
      6: { halign: 'center' },
      7: { halign: 'right' },
      8: { halign: 'right' },
      9: { halign: 'right' },
      10: { halign: 'right' },
      11: { halign: 'right' },
      12: { halign: 'right' },
    },
  })

  addPageNumbers(doc)
  doc.save(`oferta-${todayISO()}.pdf`)
}

// ─────────────────────────────────────────────────
// PROYECCIÓN PDF
// ─────────────────────────────────────────────────

export function exportProyeccionPDF(proyeccion) {
  if (!proyeccion || !proyeccion.dias) return

  const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' })

  const fechaInicio = proyeccion.dias[0]?.fecha || ''
  let y = addHeader(doc, 'Reporte de Proyección Semanal', `Semana del ${fechaInicio} — Total: ${formatNumber(proyeccion.total_pollos_semana)} pollos — Cajas: ${formatNumber(proyeccion.produccion_cajas_semanales)}`)

  const { dias } = proyeccion
  const bodyRows = []

  dias.forEach((dia, diaIdx) => {
    dia.lotes.forEach((lote) => {
      bodyRows.push({
        content: [
          DIAS_SEMANA[diaIdx],
          dia.fecha || '-',
          lote.granja,
          lote.galpon,
          lote.nucleo,
          formatNumber(lote.cantidad),
          lote.sexo || '-',
          lote.edad_fin_retiro ?? '-',
          lote.diferencia_edad_ideal != null ? (lote.diferencia_edad_ideal > 0 ? '+' : '') + lote.diferencia_edad_ideal : '-',
          lote.peso_vivo_retiro?.toFixed(2) ?? '-',
          lote.peso_faenado?.toFixed(2) ?? '-',
          lote.calibre_promedio?.toFixed(2) ?? '-',
          formatNumber(lote.cajas),
        ],
        isSubtotal: false,
      })
    })
    // Subtotal row
    bodyRows.push({
      content: [
        `Subtotal ${DIAS_SEMANA[diaIdx]}`,
        '',
        '',
        '',
        '',
        formatNumber(dia.total_pollos),
        '',
        '',
        dia.diferencia_edad_promedio?.toFixed(1) ?? '',
        dia.peso_promedio_ponderado?.toFixed(2) ?? '',
        '',
        dia.calibre_promedio_ponderado?.toFixed(2) ?? '',
        formatNumber(dia.cajas_totales),
      ],
      isSubtotal: true,
    })
  })

  doc.autoTable({
    startY: y,
    head: [['Día', 'Fecha', 'Granja', 'Galpón', 'Núcleo', 'Cantidad', 'Sexo', 'Edad Fin', 'Dif. Edad', 'Peso Vivo', 'Peso Faen.', 'Calibre', 'Cajas']],
    body: bodyRows.map(r => r.content),
    ...tableStyles(),
    columnStyles: {
      0: { fontStyle: 'bold', halign: 'left' },
      2: { fontStyle: 'bold', halign: 'left' },
      3: { halign: 'center' },
      4: { halign: 'center' },
      5: { halign: 'right' },
      6: { halign: 'center' },
      7: { halign: 'right' },
      8: { halign: 'right' },
      9: { halign: 'right' },
      10: { halign: 'right' },
      11: { halign: 'right' },
      12: { halign: 'right' },
    },
    didParseCell: (data) => {
      if (data.section === 'body') {
        const rowInfo = bodyRows[data.row.index]
        if (rowInfo && rowInfo.isSubtotal) {
          data.cell.styles.fillColor = SUBTOTAL_BG
          data.cell.styles.fontStyle = 'bold'
          data.cell.styles.textColor = TEXT
        }
      }
    },
  })

  // Unassigned lots
  const lotesNA = proyeccion.lotes_no_asignados || []
  if (lotesNA.length > 0) {
    y = doc.lastAutoTable.finalY + 10

    if (y > doc.internal.pageSize.getHeight() - 40) {
      doc.addPage()
      y = 20
    }

    doc.setFontSize(10)
    doc.setFont('helvetica', 'bold')
    doc.setTextColor(245, 158, 11) // warning color
    doc.text(`Lotes no asignados (${lotesNA.length} lotes — ${formatNumber(proyeccion.total_pollos_no_asignados || 0)} pollos)`, 20, y)
    y += 4

    const naRows = lotesNA.map(l => [
      l.granja,
      l.galpon,
      l.nucleo,
      formatNumber(l.cantidad),
      l.dias_elegibles ? l.dias_elegibles.map(d => {
        const fecha = new Date(d + 'T12:00:00')
        const idx = (fecha.getDay() + 6) % 7
        return DIAS_SEMANA[idx] || d
      }).join(', ') : '-',
      l.motivo || '-',
    ])

    doc.autoTable({
      startY: y,
      head: [['Granja', 'Galpón', 'Núcleo', 'Cantidad', 'Días Elegibles', 'Motivo']],
      body: naRows,
      ...tableStyles(),
      headStyles: {
        ...tableStyles().headStyles,
        fillColor: [245, 158, 11],
      },
      columnStyles: {
        0: { fontStyle: 'bold', halign: 'left' },
        1: { halign: 'center' },
        2: { halign: 'center' },
        3: { halign: 'right' },
        4: { halign: 'left' },
        5: { halign: 'left' },
      },
    })
  }

  addPageNumbers(doc)
  doc.save(`proyeccion-semana-${fechaInicio || todayISO()}.pdf`)
}

// ─────────────────────────────────────────────────
// RESUMEN SEMANAL PDF
// ─────────────────────────────────────────────────

export function exportResumenPDF(proyeccion) {
  if (!proyeccion || !proyeccion.dias) return

  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
  const pageWidth = doc.internal.pageSize.getWidth()

  const fechaInicio = proyeccion.dias[0]?.fecha || ''
  let y = addHeader(doc, 'Resumen Semanal', `Semana del ${fechaInicio}`)

  const { dias } = proyeccion

  // Stats boxes
  const stats = [
    ['Total Pollos', formatNumber(proyeccion.total_pollos_semana)],
    ['Sofía', formatNumber(proyeccion.sofia)],
    ['Prom. Edad', `${proyeccion.promedio_edad_semana?.toFixed(1)} días`],
    ['Cajas Semanales', formatNumber(proyeccion.produccion_cajas_semanales)],
  ]

  doc.setFontSize(9)
  const boxWidth = (pageWidth - 40 - 15) / 4
  stats.forEach(([label, value], i) => {
    const x = 20 + i * (boxWidth + 5)
    doc.setFillColor(...ROW_ALT)
    doc.roundedRect(x, y, boxWidth, 16, 2, 2, 'F')
    doc.setDrawColor(...PRIMARY)
    doc.setLineWidth(0.5)
    doc.line(x, y, x, y + 16)

    doc.setTextColor(...TEXT_LIGHT)
    doc.setFont('helvetica', 'normal')
    doc.setFontSize(7)
    doc.text(label.toUpperCase(), x + 4, y + 5)

    doc.setTextColor(...PRIMARY)
    doc.setFont('helvetica', 'bold')
    doc.setFontSize(11)
    doc.text(value, x + 4, y + 13)
  })

  y += 24

  // Daily summary table
  doc.setFontSize(10)
  doc.setFont('helvetica', 'bold')
  doc.setTextColor(...PRIMARY)
  doc.text('Resumen Diario', 20, y)
  y += 4

  const dailyRows = dias.map((dia, idx) => [
    DIAS_SEMANA[idx],
    dia.fecha || '-',
    formatNumber(dia.total_pollos),
    dia.lotes.filter(l => l.cantidad > 0).length,
    `${dia.peso_promedio_ponderado?.toFixed(2)} kg`,
    dia.diferencia_edad_promedio?.toFixed(1) ?? '-',
    dia.calibre_promedio_ponderado?.toFixed(2) ?? '-',
    formatNumber(dia.cajas_totales),
  ])

  // Total row
  const totalRow = [
    'TOTAL SEMANA',
    '',
    formatNumber(proyeccion.total_pollos_semana),
    dias.reduce((sum, d) => sum + d.lotes.filter(l => l.cantidad > 0).length, 0),
    '',
    '',
    '',
    formatNumber(proyeccion.produccion_cajas_semanales),
  ]

  doc.autoTable({
    startY: y,
    head: [['Día', 'Fecha', 'Pollos', 'Lotes', 'Peso Prom.', 'Dif. Edad', 'Calibre', 'Cajas']],
    body: [...dailyRows, totalRow],
    ...tableStyles(),
    columnStyles: {
      0: { fontStyle: 'bold', halign: 'left' },
      1: { halign: 'center' },
      2: { halign: 'right' },
      3: { halign: 'center' },
      4: { halign: 'right' },
      5: { halign: 'right' },
      6: { halign: 'right' },
      7: { halign: 'right' },
    },
    didParseCell: (data) => {
      if (data.section === 'body' && data.row.index === dailyRows.length) {
        data.cell.styles.fillColor = SUBTOTAL_BG
        data.cell.styles.fontStyle = 'bold'
      }
    },
  })

  y = doc.lastAutoTable.finalY + 10

  // Distribution by farm
  doc.setFontSize(10)
  doc.setFont('helvetica', 'bold')
  doc.setTextColor(...PRIMARY)
  doc.text('Distribución por Granja', 20, y)
  y += 4

  const porGranja = {}
  dias.forEach((dia, diaIdx) => {
    dia.lotes.forEach(lote => {
      if (!porGranja[lote.granja]) {
        porGranja[lote.granja] = { dias: new Array(dias.length).fill(0), total: 0, cajas: 0 }
      }
      porGranja[lote.granja].dias[diaIdx] += lote.cantidad
      porGranja[lote.granja].total += lote.cantidad
      porGranja[lote.granja].cajas += lote.cajas
    })
  })

  const farmHeaders = ['Granja', ...dias.map((_, idx) => DIAS_SEMANA[idx]), 'Total', 'Cajas']
  const farmBody = Object.entries(porGranja)
    .sort((a, b) => b[1].total - a[1].total)
    .map(([granja, info]) => [
      granja,
      ...info.dias.map(c => c > 0 ? formatNumber(c) : '-'),
      formatNumber(info.total),
      formatNumber(Math.round(info.cajas)),
    ])

  const farmTotalRow = [
    'TOTAL',
    ...dias.map(d => formatNumber(d.total_pollos)),
    formatNumber(proyeccion.total_pollos_semana),
    formatNumber(proyeccion.produccion_cajas_semanales),
  ]

  const farmColStyles = { 0: { fontStyle: 'bold', halign: 'left' } }
  for (let i = 1; i < farmHeaders.length; i++) {
    farmColStyles[i] = { halign: 'right' }
  }

  doc.autoTable({
    startY: y,
    head: [farmHeaders],
    body: [...farmBody, farmTotalRow],
    ...tableStyles(),
    columnStyles: farmColStyles,
    didParseCell: (data) => {
      if (data.section === 'body' && data.row.index === farmBody.length) {
        data.cell.styles.fillColor = SUBTOTAL_BG
        data.cell.styles.fontStyle = 'bold'
      }
    },
  })

  addPageNumbers(doc)
  doc.save(`resumen-semana-${fechaInicio || todayISO()}.pdf`)
}

// ─────────────────────────────────────────────────
// PARÁMETROS PDF
// ─────────────────────────────────────────────────

export function exportParametrosPDF(params) {
  if (!params) return

  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' })
  const pageWidth = doc.internal.pageSize.getWidth()

  let y = addHeader(doc, 'Parámetros de Cálculo')

  const sections = [
    {
      title: 'Ganancia de Peso',
      items: [
        ['Ganancia diaria machos (kg)', params.ganancia_diaria_macho],
        ['Ganancia diaria hembras (kg)', params.ganancia_diaria_hembra],
        ['Factor medio día', params.medio_dia_ganancia],
      ],
    },
    {
      title: 'Rendimiento',
      items: [
        ['Rendimiento canal (%)', params.rendimiento_canal],
        ['Kg por caja', params.kg_por_caja],
        ['Descuento sin sexar (%)', params.descuento_sin_sexar],
      ],
    },
    {
      title: 'Edades Ideales',
      items: [
        ['Edad ideal machos (días)', params.edad_ideal_macho],
        ['Edad ideal hembras (días)', params.edad_ideal_hembra],
        ['Edad ideal sin sexar (días)', params.edad_ideal_sin_sexar],
        ['Edad mínima faena (días)', params.edad_min_faena],
        ['Edad máxima faena (días)', params.edad_max_faena],
      ],
    },
    {
      title: 'Rango de Peso Faena',
      items: [
        ['Peso mínimo faena (kg)', params.peso_min_faena],
        ['Peso máximo faena (kg)', params.peso_max_faena],
      ],
    },
    {
      title: 'Producción',
      items: [
        ['Pollos diarios mín.', formatNumber(params.pollos_diarios_objetivo_min)],
        ['Pollos diarios máx.', formatNumber(params.pollos_diarios_objetivo_max)],
        ['Descuento Sofía', formatNumber(params.descuento_sofia)],
      ],
    },
  ]

  sections.forEach((section) => {
    doc.setFontSize(10)
    doc.setFont('helvetica', 'bold')
    doc.setTextColor(...PRIMARY)
    doc.text(section.title, 20, y)
    y += 4

    const tableWidth = Math.min(pageWidth - 40, 160)
    const marginLeft = (pageWidth - tableWidth) / 2

    doc.autoTable({
      startY: y,
      head: [['Parámetro', 'Valor']],
      body: section.items.map(([label, value]) => [label, value ?? '-']),
      ...tableStyles(),
      tableWidth: tableWidth,
      margin: { left: marginLeft, right: marginLeft },
      columnStyles: {
        0: { halign: 'left', cellWidth: tableWidth * 0.7 },
        1: { halign: 'center', fontStyle: 'bold' },
      },
    })

    y = doc.lastAutoTable.finalY + 8
  })

  addPageNumbers(doc)
  doc.save(`parametros-${todayISO()}.pdf`)
}
