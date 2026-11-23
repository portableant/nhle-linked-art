    function commonsFilePageUrl(rawImageUrl) {
      if (!rawImageUrl) return '';
      try {
        const filename = decodeURIComponent(rawImageUrl.split('/').pop().replace(/^\d+px-/, ''));
        return `https://commons.wikimedia.org/wiki/File:${encodeURIComponent(filename)}`;
      } catch (e) {
        return rawImageUrl;
      }
    }

    function resolveRepresentationImageUrl(doc) {
      const reps = Array.isArray(doc?.representation) ? doc.representation : (doc?.representation ? [doc.representation] : []);
      for (const rep of reps) {
        if (!rep) continue;
        // 1. Standard Linked Art VisualItem -> digitally_shown_by -> DigitalObject -> access_point
        const shownBy = Array.isArray(rep.digitally_shown_by) ? rep.digitally_shown_by : (rep.digitally_shown_by ? [rep.digitally_shown_by] : []);
        for (const dig of shownBy) {
          const aps = Array.isArray(dig?.access_point) ? dig.access_point : (dig?.access_point ? [dig.access_point] : []);
          for (const ap of aps) {
            const candidate = typeof ap === 'string' ? ap : ap?.id;
            if (candidate && /^https?:\/\//i.test(candidate) && !candidate.includes('/api/visual/') && !candidate.includes('/api/digital/')) {
              return candidate.replace(/^http:\/\//i, 'https://');
            }
          }
        }
        // 2. Direct DigitalObject representation with access_point
        const directAps = Array.isArray(rep.access_point) ? rep.access_point : (rep.access_point ? [rep.access_point] : []);
        for (const ap of directAps) {
          const candidate = typeof ap === 'string' ? ap : ap?.id;
          if (candidate && /^https?:\/\//i.test(candidate) && !candidate.includes('/api/visual/') && !candidate.includes('/api/digital/')) {
            return candidate.replace(/^http:\/\//i, 'https://');
          }
        }
      }
      return '';
    }

    function renderMediaFallback(mediaBody, fileLink, primaryName) {
      fileLink.classList.add('hidden');
      const searchQuery = encodeURIComponent(`${primaryName} ${activeId}`);
      mediaBody.innerHTML = `
        <div class="p-4 text-center space-y-2">
          <p class="text-[11px] text-slate-500 dark:text-slate-400">No playable Wikimedia Commons image available.</p>
          <a href="https://commons.wikimedia.org/w/index.php?search=${searchQuery}&title=Special:MediaSearch&type=image" target="_blank" rel="noopener noreferrer" class="inline-block px-2.5 py-1 rounded text-[11px] font-medium bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-200 hover:bg-sky-700 hover:text-white transition-colors">
            Search Wikimedia Commons &nearr;
          </a>
        </div>
      `;
    }

    function renderMediaCard(doc, primaryName) {
      const mediaBody = document.getElementById('mediaBody');
      const fileLink = document.getElementById('commonsFileLink');
      const imgUrl = resolveRepresentationImageUrl(doc);

      if (imgUrl) {
        const filePage = commonsFilePageUrl(imgUrl);
        fileLink.href = filePage;
        fileLink.classList.remove('hidden');
        mediaBody.innerHTML = `
          <button type="button" id="openLightboxBtn" class="group relative w-full h-full flex items-center justify-center focus:outline-none">
            <img id="mediaCardImg" src="${imgUrl}" alt="${primaryName}" class="w-full h-[180px] object-cover group-hover:opacity-90 transition-opacity" loading="lazy" />
            <span class="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-slate-950/80 text-[10px] font-medium text-white opacity-90 group-hover:opacity-100">
              Expand &nearr;
            </span>
          </button>
        `;
        const imgEl = document.getElementById('mediaCardImg');
        if (imgEl) {
          imgEl.addEventListener('error', () => renderMediaFallback(mediaBody, fileLink, primaryName), { once: true });
        }
        document.getElementById('openLightboxBtn').addEventListener('click', () => {
          document.getElementById('lightboxImg').src = imgUrl;
          document.getElementById('lightboxImg').alt = primaryName;
          document.getElementById('lightboxCaption').textContent = `${primaryName} (NHLE #${activeId})`;
          document.getElementById('lightboxCommonsLink').href = filePage;
          document.getElementById('imageLightbox').classList.remove('hidden');
          document.getElementById('imageLightbox').classList.add('flex');
        });
      } else {
        renderMediaFallback(mediaBody, fileLink, primaryName);
      }
    }

    document.getElementById('closeLightboxBtn').addEventListener('click', () => {
      document.getElementById('imageLightbox').classList.add('hidden');
      document.getElementById('imageLightbox').classList.remove('flex');
    });
    document.getElementById('imageLightbox').addEventListener('click', (e) => {
      if (e.target.id === 'imageLightbox') {
        document.getElementById('imageLightbox').classList.add('hidden');
        document.getElementById('imageLightbox').classList.remove('flex');
      }
    });

    function renderMiniMap(doc) {
      const wkt = doc.current_location?.defined_by || '';
      const wktLabel = document.getElementById('wktCoordsLabel');
      const match = wkt.match(/POINT\(([\-0-9.]+)\s+([\-0-9.]+)\)/);
      if (!match) {
        wktLabel.textContent = 'No coordinates';
        return;
      }
      const lon = parseFloat(match[1]);
      const lat = parseFloat(match[2]);
      wktLabel.textContent = `${lat.toFixed(4)}, ${lon.toFixed(4)}`;

      const isDark = document.documentElement.classList.contains('dark');
      const styleUrl = isDark
        ? 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
        : 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';

      if (!mapInstance) {
        mapInstance = new maplibregl.Map({
          container: 'miniMap',
          style: styleUrl,
          center: [lon, lat],
          zoom: 14,
          attributionControl: false
        });
        mapInstance.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
        activeMarker = new maplibregl.Marker({ color: '#f59e0b' }).setLngLat([lon, lat]).addTo(mapInstance);
      } else {
        mapInstance.flyTo({ center: [lon, lat], zoom: 14, essential: true });
        if (activeMarker) activeMarker.setLngLat([lon, lat]);
      }
    }

    function renderDossierCard(doc) {
      const ts = (doc.attributed_by || [])[0]?.timespan;
      const begin = ts?.begin_of_the_begin ? ts.begin_of_the_begin.slice(0, 10) : '';
      document.getElementById('designationDateLabel').textContent = begin ? `• Listed ${begin}` : '';

      const prodRow = document.getElementById('productionRow');
      const prodVal = document.getElementById('productionValue');
      const prod = doc.produced_by;
      if (prod && ((prod.carried_out_by && prod.carried_out_by.length) || prod.timespan)) {
        const actors = (prod.carried_out_by || []).map(a => a._label).join(', ');
        const span = prod.timespan?._label || '';
        prodVal.textContent = [actors, span].filter(Boolean).join(' • ');
        prodRow.classList.remove('hidden');
      } else {
        prodRow.classList.add('hidden');
      }

      const refs = doc.referred_to_by || [];
      const primaryRef = refs.find(r => r.classified_as?.[0]?._label === 'Summary') || refs[0];
      document.getElementById('dossierText').textContent = primaryRef?.content || 'No description text available.';
    }

    function extractTimelineEvents(doc) {
      const events = [];

      // 1. Primary Production (`produced_by`)
      if (doc.produced_by) {
        const p = doc.produced_by;
        const ts = p.timespan || {};
        const startYear = ts.begin_of_the_begin ? parseInt(ts.begin_of_the_begin.slice(0, 4), 10) : 9999;
        const actors = (p.carried_out_by || []).map(a => a._label).join(', ');
        events.push({
          sortYear: startYear,
          dateLabel: ts._label || (startYear !== 9999 ? String(startYear) : 'Origin'),
          kind: 'production',
          title: actors ? `Origin (${actors})` : 'Initial Construction',
          detail: p._label || 'Original fabric & construction',
        });
      }

      // 2. Subsequent Modifications (`modified_by`)
      (doc.modified_by || []).forEach(m => {
        const ts = m.timespan || {};
        const startYear = ts.begin_of_the_begin ? parseInt(ts.begin_of_the_begin.slice(0, 4), 10) : 9999;
        const rawLabel = m._label || '';
        const colonIdx = rawLabel.indexOf(':');
        const detail = colonIdx > -1 ? rawLabel.slice(colonIdx + 1).trim() : rawLabel;
        events.push({
          sortYear: startYear,
          dateLabel: ts._label || (startYear !== 9999 ? String(startYear) : 'Alteration'),
          kind: 'modification',
          title: 'Alteration / Phase',
          detail: detail || 'Recorded architectural modification',
        });
      });

      // 3. Statutory Designation & Amendments (`attributed_by`)
      (doc.attributed_by || []).forEach(attr => {
        const ts = attr.timespan || {};
        if (ts.begin_of_the_begin) {
          const dStr = ts.begin_of_the_begin.slice(0, 10);
          events.push({
            sortYear: parseInt(dStr.slice(0, 4), 10),
            dateLabel: dStr,
            kind: 'statutory',
            title: 'Statutory Listing',
            detail: attr._label || 'Added to the National Heritage List for England',
          });
        }
        if (ts.end_of_the_end) {
          const dEnd = ts.end_of_the_end.slice(0, 10);
          events.push({
            sortYear: parseInt(dEnd.slice(0, 4), 10),
            dateLabel: dEnd,
            kind: 'statutory',
            title: 'List Amendment',
            detail: 'Most recent statutory list entry amendment',
          });
        }
      });

      return events.sort((a, b) => a.sortYear - b.sortYear);
    }

    function renderTimeline(doc) {
      const track = document.getElementById('timelineTrack');
      const events = extractTimelineEvents(doc);

      if (!events.length) {
        track.innerHTML = '<p class="text-xs text-slate-400">No dated events extracted for this record.</p>';
        return;
      }

      const badgeStyles = {
        production: 'border-amber-500/60 bg-amber-50/70 dark:bg-amber-950/30 text-amber-800 dark:text-amber-300 dot:bg-amber-500',
        modification: 'border-purple-500/60 bg-purple-50/70 dark:bg-purple-950/30 text-purple-800 dark:text-purple-300 dot:bg-purple-500',
        statutory: 'border-sky-500/60 bg-sky-50/70 dark:bg-sky-950/30 text-sky-800 dark:text-sky-300 dot:bg-sky-500',
      };

      const dotColor = {
        production: 'bg-amber-500 ring-amber-500/25',
        modification: 'bg-purple-500 ring-purple-500/25',
        statutory: 'bg-sky-500 ring-sky-500/25',
      };

      track.innerHTML = `
        <div class="relative flex items-stretch gap-3 min-w-max pt-2">
          <div class="absolute left-4 right-4 top-[13px] h-0.5 bg-slate-200 dark:bg-slate-800 z-0"></div>
          ${events.map((ev, idx) => `
            <button type="button" data-ev-idx="${idx}" class="timeline-node relative z-10 w-52 text-left group focus:outline-none">
              <div class="flex items-center gap-2 mb-1.5">
                <span class="w-3 h-3 rounded-full ring-4 ${dotColor[ev.kind]} shrink-0"></span>
                <span class="text-xs font-mono font-semibold text-slate-800 dark:text-slate-100">${ev.dateLabel}</span>
              </div>
              <div class="p-2.5 rounded-md border ${badgeStyles[ev.kind]} group-hover:brightness-110 transition-all h-[76px] flex flex-col justify-between">
                <div class="text-[11px] font-semibold truncate">${ev.title}</div>
                <p class="text-[11px] text-slate-600 dark:text-slate-300 line-clamp-2 leading-snug">${ev.detail}</p>
              </div>
            </button>
          `).join('')}
        </div>
      `;

      // Clicking a timeline milestone switches the LinkedArtViewer to Graph mode so the user can inspect the TimeSpan node
      document.querySelectorAll('.timeline-node').forEach(btn => {
        btn.addEventListener('click', () => {
          if (viewerInstance && typeof viewerInstance.setMode === 'function') {
            viewerInstance.setMode('graph');
          }
        });
      });
    }

    function renderEntityRibbon(doc) {
      const matContainer = document.getElementById('ribbonMaterials');
      const perContainer = document.getElementById('ribbonPeriods');
      const catItem = catalog.find(c => c.id === activeId);

      // Materials from Linked Art `made_of` (or catalog fallback)
      const docMats = (doc.made_of || []).map(m => ({ label: m._label, uri: m.id }));
      const mats = docMats.length
        ? docMats
        : ((catItem?.materials || []).map(label => ({ label, uri: '' })));

      matContainer.innerHTML = mats.length
        ? mats.map(m => `<button type="button" data-mat="${m.label.replace(/"/g, '&quot;')}" class="ribbon-mat-chip inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-50 dark:bg-amber-950/50 text-amber-800 dark:text-amber-300 border border-amber-200 dark:border-amber-800/70 hover:border-amber-500 transition-colors" title="Filter catalog by material: ${m.label}${m.uri ? ' (' + m.uri + ')' : ''}">${m.label}</button>`).join('')
        : '<span class="text-[11px] text-slate-400 italic">None recorded</span>';

      // Periods from catalog index + Linked Art `produced_by` / `modified_by` timespans
      const periodSet = new Set(catItem?.periods || []);
      if (periodSet.has('Unassigned Period') && periodSet.size > 1) {
        periodSet.delete('Unassigned Period');
      }
      if (periodSet.size === 0) {
        if (doc.produced_by?.timespan?._label) periodSet.add(doc.produced_by.timespan._label);
        (doc.modified_by || []).forEach(m => {
          if (m.timespan?._label) periodSet.add(m.timespan._label);
        });
      }
      const periods = [...periodSet].filter(p => p && p !== 'Unassigned Period');

      perContainer.innerHTML = periods.length
        ? periods.map(p => `<button type="button" data-period="${p.replace(/"/g, '&quot;')}" class="ribbon-period-chip inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-indigo-50 dark:bg-indigo-950/50 text-indigo-800 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-800/70 hover:border-indigo-500 transition-colors" title="Filter catalog by period: ${p}">${p}</button>`).join('')
        : '<span class="text-[11px] text-slate-400 italic">Unassigned</span>';

      document.querySelectorAll('.ribbon-mat-chip').forEach(btn => {
        btn.addEventListener('click', () => {
          const val = btn.dataset.mat;
          state.material = (state.material === val) ? '' : val;
          const sel = document.getElementById('materialSelect');
          if (sel) sel.value = state.material;
          renderLimit = 100;
          renderList();
        });
      });

      document.querySelectorAll('.ribbon-period-chip').forEach(btn => {
        btn.addEventListener('click', () => {
          const val = btn.dataset.period;
          const sel = document.getElementById('periodSelect');
          if (sel && [...sel.options].some(o => o.value === val)) {
            state.period = (state.period === val) ? '' : val;
            sel.value = state.period;
          } else {
            state.q = val;
            document.getElementById('searchInput').value = val;
          }
          renderLimit = 100;
          renderList();
        });
      });
    }

    function updateHeaderMeta(doc) {
      if (!doc) return;
      const primaryName = (doc.identified_by || []).find(i => i.type === 'Name')?.content || doc._label;
      const gradeConcept = (doc.classified_as || []).find(c => c.id && c.id.includes('/concept/'));
      document.getElementById('activeTitle').textContent = primaryName;
      document.title = `${primaryName} (NHLE #${activeId}) — NHLE Linked Art 1.0`;
      document.getElementById('activeGrade').textContent = gradeConcept ? gradeConcept._label.replace(' Listed Building', '') : 'Listed';

      const imgBadge = document.getElementById('imageBadge');
      if (doc.representation && doc.representation.length > 0) {
        imgBadge.classList.remove('hidden');
      } else {
        imgBadge.classList.add('hidden');
      }

      const linksEl = document.getElementById('outboundLinks');
      const pills = [];

      (doc.subject_of || []).forEach(s => {
        let label = 'External Link';
        if (s.id.includes('historicengland.org.uk')) label = 'Historic England';
        else if (s.id.includes('wikipedia.org')) label = 'Wikipedia';
        else if (s.id.includes('commons.wikimedia.org')) label = 'Commons Category';
        else if (s.id.includes('geograph.org.uk')) label = 'Geograph UK';
        pills.push(`<a href="${s.id}" target="_blank" rel="noopener noreferrer" class="px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 hover:bg-sky-50 dark:hover:bg-sky-950/60 text-slate-700 dark:text-slate-300 hover:text-sky-600 dark:hover:text-sky-400 transition-colors">${label} &nearr;</a>`);
      });

      (doc.equivalent || []).forEach(eq => {
        const qid = eq.id.split('/').pop();
        pills.push(`<a href="${eq.id}" target="_blank" rel="noopener noreferrer" class="px-2 py-0.5 rounded bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 hover:underline font-mono">Wikidata ${qid} &nearr;</a>`);
      });

      const catItem = catalog.find(c => c.id === activeId);
      if (catItem && catItem.lat && catItem.lon) {
        pills.push(`<a href="https://www.openstreetmap.org/?mlat=${catItem.lat}&mlon=${catItem.lon}#map=17/${catItem.lat}/${catItem.lon}" target="_blank" rel="noopener noreferrer" class="px-2 py-0.5 rounded bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 hover:underline">OpenStreetMap &nearr;</a>`);
      }

      linksEl.innerHTML = pills.join('');

      renderEntityRibbon(doc);
      renderMediaCard(doc, primaryName);
      renderMiniMap(doc);
      renderDossierCard(doc);
      renderTimeline(doc);
      loadMissingPiecesForActive(activeId);
    }

    async function enrichSingleWithWikidata(id) {
      const doc = docsCache[id];
      if (!doc || (doc.equivalent && doc.equivalent.length > 0)) return;
      const query = `
        PREFIX schema: <http://schema.org/>
        SELECT ?item ?itemLabel ?image ?commonsCat ?geograph ?wikipedia WHERE {
          ?item wdt:P1216 "${id}" .
          OPTIONAL { ?item wdt:P18 ?image . }
          OPTIONAL { ?item wdt:P373 ?commonsCat . }
          OPTIONAL { ?item wdt:P1261 ?geograph . }
          OPTIONAL { ?wikipedia schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> . }
          SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
        } LIMIT 1
      `;
      try {
        const res = await fetch(`https://query.wikidata.org/sparql?format=json&query=${encodeURIComponent(query)}`);
        if (!res.ok) return;
        const payload = await res.json();
        const b = payload.results?.bindings?.[0];
        if (!b) return;

        const qidUri = b.item.value;
        const qid = qidUri.split('/').pop();
        const label = b.itemLabel?.value || qid;
        const imgUrl = b.image?.value ? b.image.value.replace(/^http:\/\//, 'https://') : '';
        const commonsCat = b.commonsCat?.value
          ? `https://commons.wikimedia.org/wiki/Category:${encodeURIComponent(b.commonsCat.value.replace(/ /g, '_'))}`
          : '';
        const geographUrl = b.geograph?.value ? `https://www.geograph.org.uk/photo/${b.geograph.value}` : '';
        const wikipediaUrl = b.wikipedia?.value || '';

        doc.equivalent = [{ id: qidUri, type: 'HumanMadeObject', _label: `${label} (${qid})` }];
        const addLink = (url, lbl) => {
          if (url && !(doc.subject_of || []).some(s => s.id === url)) {
            doc.subject_of.push({ id: url, type: 'LinguisticObject', _label: lbl, format: 'text/html' });
          }
        };
        addLink(wikipediaUrl, `Wikipedia Article: ${label}`);
        addLink(commonsCat, 'Wikimedia Commons Media Category');
        addLink(geographUrl, 'Geograph Britain and Ireland Photograph Page');
        if (imgUrl && !doc.representation) {
          doc.representation = [{
            id: `${window.location.origin}/api/visual/nhle-${id}`,
            type: 'VisualItem',
            _label: `Photograph of ${label} (Wikimedia Commons)`,
            digitally_shown_by: [{
              id: `${window.location.origin}/api/digital/nhle-${id}`,
              type: 'DigitalObject',
              format: 'image/jpeg',
              access_point: [{ id: imgUrl, type: 'DigitalObject' }]
            }]
          }];
        }

        const catItem = catalog.find(c => c.id === id);
        if (catItem) {
          catItem.wikidataUri = qidUri;
          catItem.wikidataQid = qid;
          if (imgUrl) catItem.hasImage = true;
        }

        if (activeId === id) {
          updateHeaderMeta(doc);
          if (viewerInstance && typeof viewerInstance.setData === 'function') {
            viewerInstance.setData(doc);
          }
          renderList();
        }
      } catch (e) {}
    }

