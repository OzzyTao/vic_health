import './style.css';
import { loadGeoJSON } from './dataLoader';
import { buildColourScale } from './colourScale';
import { createMapRenderer } from './mapRenderer';
import { createScorePanel } from './scorePanel';

const DATA_URL = './data/liveability.geojson';

async function init(): Promise<void> {
  const errorBanner = document.getElementById('error-banner');

  // Load GeoJSON data (Req 1.3)
  const { features, error } = await loadGeoJSON(DATA_URL);

  if (error) {
    // Display descriptive error in the UI (Req 1.4)
    if (errorBanner) {
      errorBanner.textContent = error;
      errorBanner.classList.add('visible');
    }
    return;
  }

  // Build colour scale from loaded scores (Req 1.1)
  const scores = features.map((f) => f.properties.liveability_score);
  const scale = buildColourScale(scores);

  // Initialise map and render choropleth (Req 1.1, 1.5)
  const renderer = createMapRenderer();
  renderer.init('map');
  renderer.renderChoropleth(features, scale);

  // Wire up score panel (Req 2.1, 2.4)
  const scorePanel = createScorePanel('score-panel');
  renderer.onMeshblockClick((props) => scorePanel.show(props));
  renderer.onMapClick(() => scorePanel.hide());
}

init();
