    function getRequestedEntityId() {
      const params = new URLSearchParams(window.location.search);
      const qId = params.get('id') || params.get('nhle') || params.get('entry');
      if (qId && /^\d+$/.test(qId.trim())) return qId.trim();
      const hashId = window.location.hash.replace(/^#(?:id=)?/, '').trim();
      if (hashId && /^\d+$/.test(hashId)) return hashId;
      return '';
    }

    function syncUrlForEntity(id, replace = false) {
      try {
        const url = new URL(window.location.href);
        url.searchParams.set('id', id);
        url.hash = '';
        if (replace) {
          window.history.replaceState({ id }, '', url.toString());
        } else if (window.location.search !== url.search) {
          window.history.pushState({ id }, '', url.toString());
        }
      } catch (e) {}
    }

    async function selectAsset(id, options = {}) {
      const { updateUrl = true, replaceUrl = false } = options;
      activeId = id;
      if (updateUrl) {
        syncUrlForEntity(id, replaceUrl);
      }
      renderList();

      let doc = docsCache[id];
      if (!doc) {
        try {
          const res = await fetch(`./api/object/${id.slice(0, 3)}/${id}.json`);
          if (res.ok) {
            doc = await res.json();
            docsCache[id] = doc;
          }
        } catch (e) {}
      }
      if (!doc) return;

      updateHeaderMeta(doc);
      if (viewerInstance && typeof viewerInstance.setData === 'function') {
        viewerInstance.setData(doc);
      }
      if (provenanceInstance && typeof provenanceInstance.setData === 'function') {
        provenanceInstance.setData(doc);
      }
      updateProvenanceBadge(doc);
      enrichSingleWithWikidata(id);
    }

    window.addEventListener('popstate', (e) => {
      const targetId = e.state?.id || getRequestedEntityId();
      if (targetId && targetId !== activeId) {
        selectAsset(targetId, { updateUrl: false });
      }
    });

    window.addEventListener('hashchange', () => {
      const targetId = getRequestedEntityId();
      if (targetId && targetId !== activeId) {
        selectAsset(targetId, { updateUrl: true, replaceUrl: true });
      }
    });

    document.getElementById('searchInput').addEventListener('input', (e) => {
      state.q = e.target.value;
      renderLimit = 100;
      renderList();
    });
    ['grade', 'place', 'material', 'architect', 'period'].forEach(key => {
      document.getElementById(`${key}Select`).addEventListener('change', (e) => {
        state[key] = e.target.value;
        renderLimit = 100;
        renderList();
      });
    });
    document.getElementById('hasImageOnly').addEventListener('change', (e) => {
      state.hasImage = e.target.checked;
      renderLimit = 100;
      renderList();
    });
    document.getElementById('resetFilters').addEventListener('click', () => {
      state.q = '';
      state.grade = '';
      state.place = '';
      state.material = '';
      state.architect = '';
      state.period = '';
      state.hasImage = false;
      document.getElementById('searchInput').value = '';
      ['gradeSelect', 'placeSelect', 'materialSelect', 'architectSelect', 'periodSelect'].forEach(id => {
        document.getElementById(id).value = '';
      });
      document.getElementById('hasImageOnly').checked = false;
      renderLimit = 100;
      renderList();
    });

    document.getElementById('copyLinkBtn').addEventListener('click', async () => {
      const url = new URL(window.location.href);
      url.searchParams.set('id', activeId);
      url.hash = '';
      await navigator.clipboard.writeText(url.toString());
      const btn = document.getElementById('copyLinkBtn');
      btn.textContent = 'Link Copied';
      setTimeout(() => btn.textContent = 'Share Link', 1400);
    });

    document.getElementById('copyUriBtn').addEventListener('click', async () => {
      const doc = docsCache[activeId];
      if (!doc) return;
      await navigator.clipboard.writeText(doc.id);
      const btn = document.getElementById('copyUriBtn');
      btn.textContent = 'Copied';
      setTimeout(() => btn.textContent = 'Copy JSON URI', 1200);
    });

    document.getElementById('downloadJsonBtn').addEventListener('click', () => {
      const doc = docsCache[activeId];
      if (!doc) return;
      const blob = new Blob([JSON.stringify(doc, null, 2)], { type: 'application/ld+json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `nhle-${activeId}-linked-art.json`;
      a.click();
      URL.revokeObjectURL(url);
    });

    document.getElementById('lookupForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const raw = document.getElementById('nhleInput').value.trim();
      if (!raw) return;
      if (docsCache[raw]) {
        selectAsset(raw);
        return;
      }
      try {
        const localRes = await fetch(`./api/object/${raw.slice(0, 3)}/${raw}.json`);
        if (localRes.ok) {
          docsCache[raw] = await localRes.json();
          selectAsset(raw);
          return;
        }
      } catch (err) {}

      try {
        const arcgisUrl = `https://services-eu1.arcgis.com/ZOdPfBS3aqqDYPUQ/arcgis/rest/services/National_Heritage_List_for_England_NHLE_v02_VIEW/FeatureServer/0/query?where=ListEntry%3D${encodeURIComponent(raw)}&outFields=*&outSR=4326&f=json`;
        const arcRes = await fetch(arcgisUrl);
        const data = await arcRes.json();
        if (data.features && data.features.length > 0) {
          const feat = data.features[0];
          const a = feat.attributes;
          const lon = feat.geometry?.x;
          const lat = feat.geometry?.y;
          const synthesized = {
            "@context": "https://linked.art/ns/v1/linked-art.json",
            "id": `${window.location.origin}/api/object/${raw.slice(0, 3)}/${raw}.json`,
            "type": "HumanMadeObject",
            "_label": `${a.Name} (${a.Parish || a.District || 'England'})`,
            "classified_as": [
              { "id": "http://vocab.getty.edu/aat/300004789", "type": "Type", "_label": "Building" },
              { "id": `${window.location.origin}/api/concept/grade-${(a.Grade || 'ii').toLowerCase().replace('*', '-star')}`, "type": "Type", "_label": `Grade ${a.Grade} Listed Building` }
            ],
            "identified_by": [
              { "type": "Name", "classified_as": [{ "id": "http://vocab.getty.edu/aat/300404670", "type": "Type", "_label": "Primary Name" }], "content": a.Name },
              { "type": "Identifier", "classified_as": [{ "id": "http://vocab.getty.edu/aat/300404626", "type": "Type", "_label": "NHLE List Entry Number" }], "content": String(a.ListEntry) }
            ],
            "current_location": {
              "id": `${window.location.origin}/api/place/nhle-${raw}`,
              "type": "Place",
              "_label": [a.Parish, a.District, a.County].filter(Boolean).join(', ') || 'England',
              ...(lon && lat ? { "defined_by": `POINT(${lon} ${lat})` } : {})
            },
            "subject_of": [
              { "id": a.Hyperlink || `https://historicengland.org.uk/listing/the-list/list-entry/${raw}`, "type": "LinguisticObject", "_label": `Historic England Official List Entry #${raw}`, "format": "text/html" }
            ]
          };
          docsCache[raw] = synthesized;
          if (!catalog.find(c => c.id === raw)) {
            catalog.unshift({
              id: raw,
              name: a.Name,
              grade: a.Grade,
              place: synthesized.current_location._label,
              materials: [],
              architects: [],
              periods: [],
              hasImage: false,
              lat,
              lon,
              uri: `api/object/${raw.slice(0, 3)}/${raw}.json`
            });
          }
          refreshDropdowns();
          selectAsset(raw);
        } else {
          alert(`NHLE List Entry #${raw} not found.`);
        }
      } catch (err) {
        alert(`Error resolving NHLE #${raw}.`);
      }
    });

    async function resolveExternalNhleId(raw) {
      const arcgisUrl = `https://services-eu1.arcgis.com/ZOdPfBS3aqqDYPUQ/arcgis/rest/services/National_Heritage_List_for_England_NHLE_v02_VIEW/FeatureServer/0/query?where=ListEntry%3D${encodeURIComponent(raw)}&outFields=*&outSR=4326&f=json`;
      const arcRes = await fetch(arcgisUrl);
      const data = await arcRes.json();
      if (data.features && data.features.length > 0) {
        const feat = data.features[0];
        const a = feat.attributes;
        const lon = feat.geometry?.x;
        const lat = feat.geometry?.y;
        const synthesized = {
          "@context": "https://linked.art/ns/v1/linked-art.json",
          "id": `${window.location.origin}/api/object/${raw.slice(0, 3)}/${raw}.json`,
          "type": "HumanMadeObject",
          "_label": `${a.Name} (${a.Parish || a.District || 'England'})`,
          "classified_as": [
            { "id": "http://vocab.getty.edu/aat/300004789", "type": "Type", "_label": "Building" },
            { "id": `${window.location.origin}/api/concept/grade-${(a.Grade || 'ii').toLowerCase().replace('*', '-star')}`, "type": "Type", "_label": `Grade ${a.Grade} Listed Building` }
          ],
          "identified_by": [
            { "type": "Name", "classified_as": [{ "id": "http://vocab.getty.edu/aat/300404670", "type": "Type", "_label": "Primary Name" }], "content": a.Name },
            { "type": "Identifier", "classified_as": [{ "id": "http://vocab.getty.edu/aat/300404626", "type": "Type", "_label": "NHLE List Entry Number" }], "content": String(a.ListEntry) }
          ],
          "current_location": {
            "id": `${window.location.origin}/api/place/nhle-${raw}`,
            "type": "Place",
            "_label": [a.Parish, a.District, a.County].filter(Boolean).join(', ') || 'England',
            ...(lon && lat ? { "defined_by": `POINT(${lon} ${lat})` } : {})
          },
          "subject_of": [
            { "id": a.Hyperlink || `https://historicengland.org.uk/listing/the-list/list-entry/${raw}`, "type": "LinguisticObject", "_label": `Historic England Official List Entry #${raw}`, "format": "text/html" }
          ]
        };
        docsCache[raw] = synthesized;
        if (!catalog.find(c => c.id === raw)) {
          catalog.unshift({
            id: raw,
            name: a.Name,
            grade: a.Grade,
            place: synthesized.current_location._label,
            materials: [],
            architects: [],
            periods: [],
            hasImage: false,
            lat,
            lon,
            uri: `api/object/${raw.slice(0, 3)}/${raw}.json`
          });
        }
        return true;
      }
      return false;
    }

    async function initCatalog() {
      try {
        const res = await fetch('./api/index/catalog.json');
        if (res.ok) {
          catalog = await res.json();
        }
      } catch (e) {}

      const requestedId = getRequestedEntityId();
      if (requestedId) {
        activeId = requestedId;
      } else if (catalog.length > 0 && !docsCache[activeId]) {
        activeId = catalog[0].id;
      }

      if (activeId && !docsCache[activeId]) {
        try {
          const itemRes = await fetch(`./api/object/${activeId.slice(0, 3)}/${activeId}.json`);
          if (itemRes.ok) {
            docsCache[activeId] = await itemRes.json();
          } else {
            await resolveExternalNhleId(activeId);
          }
        } catch (e) {
          try { await resolveExternalNhleId(activeId); } catch (err) {}
        }
      }

      refreshDropdowns();
      renderList();
      initViewer();
      if (docsCache[activeId]) {
        syncUrlForEntity(activeId, true);
        updateHeaderMeta(docsCache[activeId]);
        enrichSingleWithWikidata(activeId);
      }
    }

