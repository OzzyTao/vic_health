export interface SubIndicator {
  name: string;
  score: number;
}

export interface MeshblockProperties {
  meshblock_id: string;
  liveability_score: number;
  sub_indicators: SubIndicator[];
}

export interface ScorePanel {
  show(props: MeshblockProperties): void;
  hide(): void;
}

export function createScorePanel(elementId: string): ScorePanel {
  const el = document.getElementById(elementId);
  if (!el) throw new Error(`ScorePanel: element #${elementId} not found`);
  const panel = el;

  function show(props: MeshblockProperties): void {
    const indicators = props.sub_indicators ?? [];

    let indicatorsHtml: string;
    if (indicators.length === 0) {
      indicatorsHtml = `<p class="score-panel__no-data">Detailed data unavailable</p>`;
    } else {
      const rows = indicators
        .map(
          (ind) =>
            `<li class="score-panel__indicator">
              <span class="score-panel__indicator-name">${escapeHtml(ind.name)}</span>
              <span class="score-panel__indicator-score">${ind.score.toFixed(1)}</span>
            </li>`
        )
        .join('');
      indicatorsHtml = `<ul class="score-panel__indicator-list">${rows}</ul>`;
    }

    panel.innerHTML = `
      <div class="score-panel__header">
        <span class="score-panel__label">Liveability Score</span>
        <span class="score-panel__overall-score">${props.liveability_score.toFixed(1)}</span>
      </div>
      <div class="score-panel__body">
        ${indicatorsHtml}
      </div>
    `;

    panel.classList.add('visible');
  }

  function hide(): void {
    panel.classList.remove('visible');
    panel.innerHTML = '';
  }

  return { show, hide };
}

function escapeHtml(str: string): string {
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
