    // =========================================================================
    // Corpus Explorer: Material (Getty AAT) x Period Matrix & Spatial Map
    // =========================================================================
    const corpusModal = document.getElementById('corpusModal');
    let corpusMapInstance = null;
    let corpusActiveTab = 'matrix';
    let ugcIndexPromise = null;

    const CHRONO_PERIOD_ORDER = [
      'Prehistoric', 'Roman', 'Anglo-Saxon / Norman',
      '12th Century', '13th Century', '14th Century', '15th Century',
      '16th Century', '17th Century', '18th Century', '19th Century', '20th Century',
      'Unassigned Period'
    ];

    function renderCorpusStats() {
      const strip = document.getElementById('corpusStatsStrip');
      const total = catalog.length;
      const uniqueMats = new Set(catalog.flatMap(c => c.materials || [])).size;
      const uniquePlaces = new Set(catalog.map(c => c.place).filter(p => p && p !== 'Unassigned Locality')).size;
      const withImg = catalog.filter(c => c.hasImage).length;
      const geolocated = catalog.filter(c => c.lat && c.lon).length;

      strip.innerHTML = `
        <div class="flex flex-wrap items-center gap-4 font-mono text-[11px]">
          <span><strong class="text-slate-900 dark:text-white">${total}</strong> HumanMadeObjects</span>
          <span><strong class="text-amber-600 dark:text-amber-400">${uniqueMats}</strong> Getty AAT Materials</span>
          <span><strong class="text-emerald-600 dark:text-emerald-400">${uniquePlaces}</strong> Localities</span>
          <span><strong class="text-sky-600 dark:text-sky-400">${geolocated}</strong> Geolocated</span>
          <span><strong class="text-rose-600 dark:text-rose-400">${withImg}</strong> With Commons Image</span>
          <span><strong id="corpusUgcCount" class="text-rose-600 dark:text-rose-400">Loading&hellip;</strong> Places with Missing Pieces Photos</span>
        </div>
        <span class="text-[11px] text-slate-400">Sources: <code>catalog.json</code>, <code>ugc.json</code></span>
      `;
      loadCorpusUgcCount();
    }

    async function loadCorpusUgcCount() {
      try {
        if (!ugcIndexPromise) {
          ugcIndexPromise = fetch('./api/index/ugc.json').then(async res => {
            if (!res.ok) throw new Error(`UGC index request failed: ${res.status}`);
            const ids = await res.json();
            if (!Array.isArray(ids)) throw new Error('Invalid UGC index');
            return new Set(ids.map(String));
          });
        }
        const ids = await ugcIndexPromise;
        const matchingIds = new Set(catalog.map(item => String(item.id)).filter(id => ids.has(id)));
        document.getElementById('corpusUgcCount').textContent = String(matchingIds.size);
      } catch (error) {
        ugcIndexPromise = null;
        document.getElementById('corpusUgcCount').textContent = 'Unavailable';
        console.error('Could not load the Missing Pieces index:', error);
      }
    }

    function renderMaterialPeriodMatrix() {
      const container = document.getElementById('matrixTableContainer');
      const matCounts = {};
      const perSet = new Set();
      const cellCounts = {};

      catalog.forEach(item => {
        const mats = item.materials || [];
        const pers = item.periods || ['Unassigned Period'];
        mats.forEach(m => {
          matCounts[m] = (matCounts[m] || 0) + 1;
          pers.forEach(p => {
            perSet.add(p);
            const key = `${m}|||${p}`;
            cellCounts[key] = (cellCounts[key] || 0) + 1;
          });
        });
      });

      const materials = Object.entries(matCounts)
        .sort((a, b) => b[1] - a[1])
        .map(([m]) => m);

      const periods = [...perSet].sort((a, b) => {
        const ia = CHRONO_PERIOD_ORDER.indexOf(a);
        const ib = CHRONO_PERIOD_ORDER.indexOf(b);
        return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
      });

      if (!materials.length || !periods.length) {
        container.innerHTML = '<div class="p-8 text-center text-xs text-slate-400">Not enough material and period metadata to build a matrix.</div>';
        return;
      }

      const maxCell = Math.max(1, ...Object.values(cellCounts));

      const headerCols = periods.map(p => `
        <th class="px-2.5 py-2 text-left font-mono text-[11px] font-semibold text-slate-600 dark:text-slate-300 border-b border-slate-200 dark:border-slate-800 whitespace-nowrap">
          <button type="button" data-col-period="${p.replace(/"/g, '&quot;')}" class="matrix-col-btn hover:text-sky-500 hover:underline" title="Filter catalog by ${p}">
            ${p === 'Unassigned Period' ? 'Unassigned' : p.replace(' Century', ' C')}
          </button>
        </th>
      `).join('');

      const bodyRows = materials.map(m => {
        const cells = periods.map(p => {
          const count = cellCounts[`${m}|||${p}`] || 0;
          if (count === 0) {
            return `<td class="px-2.5 py-2 text-center font-mono text-[11px] text-slate-300 dark:text-slate-700 border-b border-slate-100 dark:border-slate-800/60">&middot;</td>`;
          }
          const ratio = count / maxCell;
          let heatCls = 'bg-amber-500/20 text-amber-900 dark:text-amber-200 hover:bg-amber-500/35';
          if (ratio >= 0.66) {
            heatCls = 'bg-amber-500 text-slate-950 font-bold hover:bg-amber-400';
          } else if (ratio >= 0.33) {
            heatCls = 'bg-amber-500/50 text-slate-950 dark:text-white font-semibold hover:bg-amber-500/70';
          }
          return `
            <td class="p-1 border-b border-slate-100 dark:border-slate-800/60 text-center">
              <button
                type="button"
                data-mat="${m.replace(/"/g, '&quot;')}"
                data-period="${p.replace(/"/g, '&quot;')}"
                class="matrix-cell-btn w-full py-1 px-2 rounded font-mono text-xs transition-colors ${heatCls}"
                title="${count} asset(s) with ${m} in ${p}"
              >
                ${count}
              </button>
            </td>
          `;
        }).join('');

        return `
          <tr class="hover:bg-slate-50/70 dark:hover:bg-slate-800/30">
            <th class="sticky left-0 z-10 bg-white dark:bg-slate-900 px-3 py-2 text-left text-xs font-medium text-slate-800 dark:text-slate-200 border-b border-r border-slate-200 dark:border-slate-800 whitespace-nowrap">
              <button type="button" data-row-mat="${m.replace(/"/g, '&quot;')}" class="matrix-row-btn hover:text-amber-500 hover:underline flex items-center justify-between gap-3 w-full">
                <span>${m}</span>
                <span class="text-[10px] font-mono text-slate-400">(${matCounts[m]})</span>
              </button>
            </th>
            ${cells}
          </tr>
        `;
      }).join('');

      container.innerHTML = `
        <table class="min-w-full border-collapse text-xs">
          <thead class="bg-slate-50 dark:bg-slate-950/70">
            <tr>
              <th class="sticky left-0 z-20 bg-slate-50 dark:bg-slate-950 px-3 py-2 text-left text-[11px] font-mono uppercase tracking-wider text-slate-500 border-b border-r border-slate-200 dark:border-slate-800">
                Getty AAT Material &darr; / Period &rarr;
              </th>
              ${headerCols}
            </tr>
          </thead>
          <tbody>${bodyRows}</tbody>
        </table>
      `;

      // Wire matrix cell & axis clicks to apply filters in main explorer
      container.querySelectorAll('.matrix-cell-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          state.q = '';
          state.grade = '';
          state.place = '';
          state.architect = '';
          state.hasImage = false;
          state.material = btn.dataset.mat;
          state.period = btn.dataset.period;
          document.getElementById('searchInput').value = '';
          document.getElementById('gradeSelect').value = '';
          document.getElementById('placeSelect').value = '';
          document.getElementById('architectSelect').value = '';
          document.getElementById('hasImageOnly').checked = false;
          document.getElementById('materialSelect').value = state.material;
          document.getElementById('periodSelect').value = state.period;
          renderLimit = 100;
          renderList();
          closeCorpusModal();
        });
      });

      container.querySelectorAll('.matrix-row-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          state.material = btn.dataset.rowMat;
          document.getElementById('materialSelect').value = state.material;
          renderLimit = 100;
          renderList();
          closeCorpusModal();
        });
      });

      container.querySelectorAll('.matrix-col-btn').forEach(btn => {
        btn.addEventListener('click', () => {
          state.period = btn.dataset.colPeriod;
          document.getElementById('periodSelect').value = state.period;
          renderLimit = 100;
          renderList();
          closeCorpusModal();
        });
      });
    }

    function renderCorpusMap() {
      const points = catalog.filter(c => typeof c.lat === 'number' && typeof c.lon === 'number');
      if (!points.length) return;

      const geojson = {
        type: 'FeatureCollection',
        features: points.map(p => ({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [p.lon, p.lat] },
          properties: {
            id: p.id,
            name: p.name,
            grade: p.grade,
            place: p.place,
            materials: (p.materials || []).join(', '),
          }
        }))
      };

      const isDark = document.documentElement.classList.contains('dark');
      const styleUrl = isDark
        ? 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
        : 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';

      const avgLon = points.reduce((s, p) => s + p.lon, 0) / points.length;
      const avgLat = points.reduce((s, p) => s + p.lat, 0) / points.length;

      if (!corpusMapInstance) {
        corpusMapInstance = new maplibregl.Map({
          container: 'corpusMapCanvas',
          style: styleUrl,
          center: [avgLon, avgLat],
          zoom: 11,
        });
        corpusMapInstance.addControl(new maplibregl.NavigationControl(), 'top-right');

        corpusMapInstance.on('load', () => {
          corpusMapInstance.addSource('nhle-corpus', { type: 'geojson', data: geojson });
          corpusMapInstance.addLayer({
            id: 'nhle-corpus-circles',
            type: 'circle',
            source: 'nhle-corpus',
            paint: {
              'circle-radius': ['interpolate', ['linear'], ['zoom'], 8, 5, 14, 9],
              'circle-color': [
                'match', ['get', 'grade'],
                'I', '#f59e0b',
                'II*', '#a855f7',
                'SM', '#10b981',
                '#0ea5e9'
              ],
              'circle-stroke-width': 1.5,
              'circle-stroke-color': '#0f172a'
            }
          });

          const bounds = new maplibregl.LngLatBounds();
          points.forEach(p => bounds.extend([p.lon, p.lat]));
          if (points.length > 1) {
            corpusMapInstance.fitBounds(bounds, { padding: 48, maxZoom: 14 });
          }

          corpusMapInstance.on('mouseenter', 'nhle-corpus-circles', () => {
            corpusMapInstance.getCanvas().style.cursor = 'pointer';
          });
          corpusMapInstance.on('mouseleave', 'nhle-corpus-circles', () => {
            corpusMapInstance.getCanvas().style.cursor = '';
          });

          corpusMapInstance.on('click', 'nhle-corpus-circles', (e) => {
            const feat = e.features?.[0];
            if (!feat) return;
            const props = feat.properties;
            const coords = feat.geometry.coordinates.slice();

            const popupHtml = `
              <div class="p-1 text-slate-900 max-w-[230px] space-y-1.5">
                <div class="text-[10px] font-mono text-slate-500">NHLE #${props.id} &bull; Grade ${props.grade}</div>
                <div class="font-semibold text-xs leading-snug">${props.name}</div>
                <div class="text-[11px] text-slate-600">${props.place}</div>
                ${props.materials ? `<div class="text-[10px] text-slate-500">${props.materials}</div>` : ''}
                <button type="button" data-jump-id="${props.id}" class="corpus-jump-btn mt-1 w-full px-2 py-1 rounded bg-sky-700 hover:bg-sky-600 text-white text-[11px] font-medium">
                  Inspect Linked Art Graph &rarr;
                </button>
              </div>
            `;

            new maplibregl.Popup({ closeButton: true, maxWidth: '260px' })
              .setLngLat(coords)
              .setHTML(popupHtml)
              .addTo(corpusMapInstance);

            setTimeout(() => {
              document.querySelectorAll('.corpus-jump-btn').forEach(b => {
                b.addEventListener('click', () => {
                  const targetId = b.dataset.jumpId;
                  closeCorpusModal();
                  selectAsset(targetId);
                });
              });
            }, 30);
          });
        });
      } else {
        const src = corpusMapInstance.getSource('nhle-corpus');
        if (src) src.setData(geojson);
        setTimeout(() => corpusMapInstance.resize(), 50);
      }
    }

    function switchCorpusTab(tab) {
      corpusActiveTab = tab;
      const matView = document.getElementById('corpusViewMatrix');
      const mapView = document.getElementById('corpusViewMap');
      const btnMat = document.getElementById('corpusTabMatrix');
      const btnMap = document.getElementById('corpusTabMap');

      if (tab === 'matrix') {
        matView.classList.remove('hidden');
        mapView.classList.add('hidden');
        btnMat.classList.add('bg-white', 'dark:bg-slate-900', 'text-slate-900', 'dark:text-white', 'shadow-xs');
        btnMat.classList.remove('text-slate-600', 'dark:text-slate-300');
        btnMap.classList.remove('bg-white', 'dark:bg-slate-900', 'text-slate-900', 'dark:text-white', 'shadow-xs');
        btnMap.classList.add('text-slate-600', 'dark:text-slate-300');
      } else {
        matView.classList.add('hidden');
        mapView.classList.remove('hidden');
        btnMap.classList.add('bg-white', 'dark:bg-slate-900', 'text-slate-900', 'dark:text-white', 'shadow-xs');
        btnMap.classList.remove('text-slate-600', 'dark:text-slate-300');
        btnMat.classList.remove('bg-white', 'dark:bg-slate-900', 'text-slate-900', 'dark:text-white', 'shadow-xs');
        btnMat.classList.add('text-slate-600', 'dark:text-slate-300');
        renderCorpusMap();
      }
    }

    function openCorpusModal() {
      renderCorpusStats();
      renderMaterialPeriodMatrix();
      corpusModal.classList.remove('hidden');
      corpusModal.classList.add('flex');
      if (corpusActiveTab === 'map') {
        renderCorpusMap();
      }
    }

    function closeCorpusModal() {
      corpusModal.classList.add('hidden');
      corpusModal.classList.remove('flex');
    }

    document.getElementById('openCorpusBtn').addEventListener('click', openCorpusModal);
    document.getElementById('closeCorpusModalBtn').addEventListener('click', closeCorpusModal);
    document.getElementById('corpusTabMatrix').addEventListener('click', () => switchCorpusTab('matrix'));
    document.getElementById('corpusTabMap').addEventListener('click', () => switchCorpusTab('map'));
    corpusModal.addEventListener('click', (e) => {
      if (e.target === corpusModal) closeCorpusModal();
    });

