"use client";

/**
 * MapLibre map for lease boundaries.
 *
 * Three things shape this component:
 *
 * 1. MapLibre is imported *inside* the effect, not at module scope. Client
 *    components are still server-rendered for the initial HTML, and maplibre-gl
 *    touches `window` on import, which would break the server render. Note that
 *    maplibre-gl v6 has no default export, so the namespace is destructured.
 *
 * 2. The basemap comes from OpenFreeMap, which needs no API key. If those tiles
 *    cannot be reached, the map swaps to an inline blank style so the lease
 *    geometry still renders rather than the whole pane going unusable.
 *
 * 3. The map is created once and only updated afterwards. Recreating it per
 *    render would drop the user's pan and zoom on every data refresh.
 */

import { useEffect, useRef, useState } from "react";
import type {
  MapLayerMouseEvent,
  Map as MapLibreMap,
  StyleSpecification,
} from "maplibre-gl";

import { Card } from "@/components/ui/card";
import type { GeoJSONGeometry, LatLon } from "@/lib/types";
import { cn } from "@/lib/utils";
import "maplibre-gl/dist/maplibre-gl.css";

const BASEMAP_STYLE = "https://tiles.openfreemap.org/styles/positron";

/** Achromatic fallback so geometry still renders when tiles are unreachable. */
const FALLBACK_STYLE: StyleSpecification = {
  version: 8,
  sources: {},
  layers: [
    { id: "background", type: "background", paint: { "background-color": "#e9e9e6" } },
  ],
};

const RISK_COLOR: Record<string, string> = {
  low: "#059669",
  medium: "#d97706",
  high: "#ea580c",
  critical: "#dc2626",
};

const SOURCE_ID = "leases";
const INTERACTIVE_LAYERS = ["lease-fill", "lease-centroid"];

/** A GeoJSON feature as this component builds them, kept minimal on purpose. */
interface MapFeature {
  type: "Feature";
  geometry: GeoJSONGeometry;
  properties: {
    id: string;
    name: string;
    lease_number: string;
    /** Present when the feature came from the GeoJSON endpoint. */
    compliance_score?: number;
    risk_level?: string;
    district?: string;
    state?: string;
  };
}

export interface MapLease {
  id: string;
  name: string;
  lease_number: string;
  /**
   * Ready-made geometry, as returned by `GET /leases/geojson`. Preferred, since
   * the server has already resolved boundary-or-centroid and the map then deals
   * in one shape instead of two.
   */
  geometry?: GeoJSONGeometry;
  /** Set when the caller holds a lease record rather than a GeoJSON feature. */
  boundary?: GeoJSONGeometry | null;
  centroid?: LatLon | null;
}

/** Popup content is built as an HTML string, so values must be escaped. */
function escapeHtml(value: string): string {
  return value.replace(
    /[&<>"']/g,
    (character) =>
      ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      })[character] as string,
  );
}

function toFeatures(leases: MapLease[]): MapFeature[] {
  return leases.flatMap((lease) => {
    const properties = {
      id: lease.id,
      name: lease.name,
      lease_number: lease.lease_number,
    };

    if (lease.geometry) {
      return [{ type: "Feature" as const, geometry: lease.geometry, properties }];
    }

    const features: MapFeature[] = [];

    if (lease.boundary) {
      features.push({ type: "Feature", geometry: lease.boundary, properties });
    }

    // The centroid is added even when a boundary exists, so every site gets a
    // pin that is tappable regardless of polygon size.
    if (lease.centroid) {
      features.push({
        type: "Feature",
        geometry: {
          type: "Point",
          coordinates: [lease.centroid.lon, lease.centroid.lat],
        },
        properties,
      });
    }

    return features;
  });
}

export function LeaseMap({
  leases,
  className,
  fitToBounds = true,
  interactive = true,
}: {
  leases: MapLease[];
  className?: string;
  fitToBounds?: boolean;
  interactive?: boolean;
}) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [degraded, setDegraded] = useState(false);
  const [ready, setReady] = useState(false);

  const features = toFeatures(leases);
  // Keyed on content so the update effect does not re-run on every render just
  // because a new array identity was passed in.
  const dataKey = JSON.stringify(features);

  useEffect(() => {
    if (!container.current || mapRef.current) return;

    let cancelled = false;
    let created: MapLibreMap | null = null;

    void (async () => {
      // v6 exposes named exports only; there is no default export.
      const { Map: MLMap, Popup, NavigationControl } = await import("maplibre-gl");
      if (cancelled || !container.current) return;

      const map = new MLMap({
        container: container.current,
        style: BASEMAP_STYLE,
        center: [78.96, 20.59], // Roughly central India, as a neutral default.
        zoom: 4,
        interactive,
        attributionControl: { compact: true },
      });

      created = map;
      mapRef.current = map;

      map.on("error", () => {
        if (degraded) return;
        setDegraded(true);
        try {
          map.setStyle(FALLBACK_STYLE);
        } catch {
          // Map may already be torn down; nothing useful to do.
        }
      });

      map.addControl(new NavigationControl({ showCompass: false }), "top-right");

      map.on("load", () => {
        if (cancelled) return;

        map.addSource(SOURCE_ID, {
          type: "geojson",
          data: { type: "FeatureCollection", features: [] },
        });

        map.addLayer({
          id: "lease-fill",
          type: "fill",
          source: SOURCE_ID,
          filter: ["in", ["geometry-type"], ["literal", ["Polygon", "MultiPolygon"]]],
          paint: { "fill-color": "#2563eb", "fill-opacity": 0.18 },
        });

        map.addLayer({
          id: "lease-outline",
          type: "line",
          source: SOURCE_ID,
          paint: { "line-color": "#1d4ed8", "line-width": 1.6 },
        });

        map.addLayer({
          id: "lease-centroid",
          type: "circle",
          source: SOURCE_ID,
          filter: ["==", ["geometry-type"], "Point"],
          paint: {
            "circle-radius": 5,
            "circle-color": "#1d4ed8",
            "circle-stroke-color": "#ffffff",
            "circle-stroke-width": 1.5,
          },
        });

        // Tapping a feature opens a popup. On a phone this is the only way to
        // inspect a site without leaving the map, so the popup carries the
        // headline figures and a link through to the full record.
        const popup = new Popup({ closeButton: true, offset: 14, maxWidth: "260px" });

        const openPopup = (event: MapLayerMouseEvent) => {
          const feature = event.features?.[0];
          if (!feature) return;

          const props = (feature.properties ?? {}) as Record<string, unknown>;
          const risk = String(props.risk_level ?? "");
          const score = props.compliance_score;

          popup
            .setLngLat(event.lngLat)
            .setHTML(
              `<div style="font:13px/1.45 system-ui,sans-serif;color:#18181b">
                 <div style="font-weight:600">${escapeHtml(String(props.name ?? ""))}</div>
                 <div style="color:#71717a;font-family:ui-monospace,monospace;font-size:11px">${escapeHtml(
                   String(props.lease_number ?? ""),
                 )}</div>
                 ${
                   score !== undefined
                     ? `<div style="margin-top:6px">Score <strong>${escapeHtml(
                         String(score),
                       )}</strong>${
                         risk
                           ? ` · <span style="color:${
                               RISK_COLOR[risk] ?? "#71717a"
                             };font-weight:600">${escapeHtml(risk)}</span>`
                           : ""
                       }</div>`
                     : ""
                 }
                 <a href="/leases/${escapeHtml(String(props.id ?? ""))}"
                    style="display:inline-block;margin-top:8px;color:#1d4ed8;font-weight:500">
                   Open record →
                 </a>
               </div>`,
            )
            .addTo(map);
        };

        for (const layer of INTERACTIVE_LAYERS) {
          map.on("click", layer, openPopup);
          // Hover affordance only; touch devices never fire these.
          map.on("mouseenter", layer, () => {
            map.getCanvas().style.cursor = "pointer";
          });
          map.on("mouseleave", layer, () => {
            map.getCanvas().style.cursor = "";
          });
        }

        setReady(true);
      });
    })();

    return () => {
      cancelled = true;
      created?.remove();
      mapRef.current = null;
      setReady(false);
    };
    // `degraded` is intentionally excluded: it is only read to avoid repeating
    // the fallback, and including it would recreate the map on first error.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interactive]);

  // Push data and viewport once the map is loaded, and whenever leases change.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready) return;

    const source = map.getSource(SOURCE_ID) as
      | { setData: (data: unknown) => void }
      | undefined;

    source?.setData({ type: "FeatureCollection", features });

    if (!fitToBounds || features.length === 0) return;

    const coordinates: number[][] = [];
    for (const feature of features) {
      const { geometry } = feature;
      if (geometry.type === "Point") {
        coordinates.push(geometry.coordinates);
      } else if (geometry.type === "Polygon") {
        for (const ring of geometry.coordinates) coordinates.push(...ring);
      } else {
        for (const polygon of geometry.coordinates)
          for (const ring of polygon) coordinates.push(...ring);
      }
    }

    if (coordinates.length === 0) return;

    const lons = coordinates.map((pair) => pair[0]);
    const lats = coordinates.map((pair) => pair[1]);

    map.fitBounds(
      [
        [Math.min(...lons), Math.min(...lats)],
        [Math.max(...lons), Math.max(...lats)],
      ],
      // Padding keeps geometry clear of the edges and the zoom control.
      { padding: 48, duration: 0, maxZoom: 12 },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dataKey, ready, fitToBounds]);

  return (
    <Card className={cn("relative overflow-hidden p-0", className)}>
      {/* The container needs a height before MapLibre initialises, otherwise it
          measures zero and renders nothing. */}
      <div ref={container} className="size-full min-h-56" />

      {degraded && (
        <p className="pointer-events-none absolute bottom-2 left-2 rounded-md bg-background/90 px-2 py-1 text-[0.6875rem] text-muted-foreground shadow-sm">
          Basemap unavailable — showing lease geometry only
        </p>
      )}
    </Card>
  );
}
