import { jsPDF } from 'jspdf';
import html2canvas from 'html2canvas';
import { createRoot } from 'react-dom/client';
import React from 'react';
import type { ReportData, ComparisonData } from '../types/domain';
import { ReportDocument } from '../components/report/ReportDocument';

export async function downloadReportPdf(
  report: ReportData,
  comparison?: ComparisonData | null
): Promise<void> {
  let targetElement = document.getElementById('report-printable-area');
  let tempContainer: HTMLDivElement | null = null;
  let rootInstance: ReturnType<typeof createRoot> | null = null;

  try {
    if (!targetElement) {
      // Создание закадрового контейнера с точной фиксированной шириной для рендеринга с высоким DPI
      tempContainer = document.createElement('div');
      tempContainer.id = 'report-pdf-temp-render';
      tempContainer.style.position = 'fixed';
      tempContainer.style.left = '-9999px';
      tempContainer.style.top = '0';
      tempContainer.style.width = '1024px';
      tempContainer.style.backgroundColor = '#ffffff';
      tempContainer.style.zIndex = '-9999';
      document.body.appendChild(tempContainer);

      rootInstance = createRoot(tempContainer);
      rootInstance.render(
        React.createElement(ReportDocument, {
          report,
          comparison,
          forPdf: true,
        })
      );

      // Ожидание отрисовки React и стабилизации шрифтов/DOM
      await new Promise((resolve) => setTimeout(resolve, 350));
      targetElement = tempContainer.querySelector('#report-printable-area') || tempContainer;
    }

    const pdf = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4',
    });

    const pageWidthMm = 210;
    const pageHeightMm = 297;

    // Определение явных секций страниц (data-pdf-page)
    const pageNodes = targetElement.querySelectorAll<HTMLElement>('[data-pdf-page]');
    const pagesToRender = pageNodes.length > 0 ? Array.from(pageNodes) : [targetElement];

    // Перерисовка карт и графиков под верстку перед захватом через html2canvas
    window.dispatchEvent(new Event('resize'));
    await new Promise((resolve) => setTimeout(resolve, 150));

    for (let i = 0; i < pagesToRender.length; i++) {
      if (i > 0) {
        pdf.addPage();
      }

      const pageEl = pagesToRender[i];
      const elWidth = pageEl.offsetWidth || 1024;
      const canvas = await html2canvas(pageEl, {
        scale: 2,
        useCORS: true,
        allowTaint: false,
        backgroundColor: '#ffffff',
        logging: false,
        width: elWidth,
        windowWidth: elWidth,
      });

      const imgData = canvas.toDataURL('image/jpeg', 0.95);
      const canvasWidth = canvas.width;
      const canvasHeight = canvas.height;
      const mmPerPx = pageWidthMm / canvasWidth;
      const imgHeightMm = canvasHeight * mmPerPx;
      let renderWidth = pageWidthMm;
      let renderHeight = imgHeightMm;
      let offsetX = 0;
      let offsetY = 0;

      // Пропорциональное уменьшение, если высота контента превышает A4 (297mm), чтобы ничего не обрезалось
      if (imgHeightMm > pageHeightMm) {
        const scaleFactor = pageHeightMm / imgHeightMm;
        renderWidth = pageWidthMm * scaleFactor;
        renderHeight = pageHeightMm;
        offsetX = (pageWidthMm - renderWidth) / 2;
      }

      pdf.addImage(imgData, 'JPEG', offsetX, offsetY, renderWidth, renderHeight);
    }

    pdf.save(`report_${report.pair_id || 'amur'}.pdf`);
  } catch (error) {
    console.error('Не удалось сформировать PDF через canvas, переход к базовому PDF:', error);
    // Запасной вариант, если захват canvas не удался
    const pdf = new jsPDF('p', 'mm', 'a4');
    pdf.setFontSize(16);
    pdf.text(report.event_name || 'HydroWatch Report', 14, 20);
    pdf.setFontSize(10);
    pdf.text(`pair_id: ${report.pair_id}`, 14, 28);
    pdf.text(`flood_ha: ${report.flood_ha} ha`, 14, 36);
    pdf.text(`water_peak_ha: ${report.water_peak_ha} ha`, 14, 44);
    pdf.save(`report_${report.pair_id || 'amur'}.pdf`);
  } finally {
    if (rootInstance) {
      try {
        rootInstance.unmount();
      } catch {
        // игнорирование ошибок размонтирования
      }
    }
    if (tempContainer && tempContainer.parentNode) {
      tempContainer.parentNode.removeChild(tempContainer);
    }
  }
}
