import type * as GeoJSON from 'geojson';

export interface SubIndicator {
  name: string;
  score: number;
}

export interface MeshblockProperties {
  meshblock_id: string;
  liveability_score: number;
  sub_indicators: SubIndicator[];
}

export interface MeshblockFeature extends GeoJSON.Feature<GeoJSON.Geometry, MeshblockProperties> {}

export interface LoadResult {
  features: MeshblockFeature[];
  error?: string;
}

export async function loadGeoJSON(url: string): Promise<LoadResult> {
  let data: GeoJSON.FeatureCollection;

  try {
    const response = await fetch(url);
    if (!response.ok) {
      return { features: [], error: `Failed to fetch GeoJSON: ${response.status} ${response.statusText}` };
    }
    data = await response.json() as GeoJSON.FeatureCollection;
  } catch (err) {
    return { features: [], error: `Failed to load GeoJSON: ${err instanceof Error ? err.message : String(err)}` };
  }

  const features: MeshblockFeature[] = [];

  for (const feature of data.features ?? []) {
    const props = feature.properties as Record<string, unknown> | null;

    if (!props || typeof props['meshblock_id'] !== 'string' || typeof props['liveability_score'] !== 'number') {
      console.warn('Skipping feature missing required fields (meshblock_id, liveability_score):', feature);
      continue;
    }

    const subIndicators: SubIndicator[] = Array.isArray(props['sub_indicators'])
      ? (props['sub_indicators'] as SubIndicator[])
      : [];

    features.push({
      ...feature,
      properties: {
        meshblock_id: props['meshblock_id'],
        liveability_score: props['liveability_score'],
        sub_indicators: subIndicators,
      },
    } as MeshblockFeature);
  }

  return { features };
}
