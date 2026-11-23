    const ViewerClass = (window.LinkedArtViewer && window.LinkedArtViewer.LinkedArtViewer) || window.LinkedArtViewer;
    const ProvenanceClass = (window.ProvenanceTimeline && window.ProvenanceTimeline.ProvenanceTimeline) || window.ProvenanceTimeline;

    function updateProvenanceBadge(doc) {
      const badge = document.getElementById('provenanceCountBadge');
      if (!badge || !doc) return;
      const count = (doc.produced_by ? 1 : 0) + (doc.changed_ownership_through?.length || 0) + (doc.current_owner?.length ? 1 : 0);
      badge.textContent = count > 0 ? String(count) : '';
    }

    function initViewer() {
      const initialTheme = document.documentElement.classList.contains('dark') ? 'dark' : 'light';
      if (typeof ViewerClass === 'function') {
        viewerInstance = new ViewerClass('#viewer', {
          data: docsCache[activeId],
          theme: initialTheme,
          showUrlInput: true,
          height: '560px',
        });
      } else {
        document.getElementById('viewer').innerHTML =
          '<div class="p-6 text-sm text-rose-500 bg-slate-900">Could not load @micropasts/linked-art-viewer UMD bundle from unpkg.</div>';
      }

      if (typeof ProvenanceClass === 'function') {
        provenanceInstance = new ProvenanceClass('#provenanceViewer', {
          data: docsCache[activeId],
          theme: initialTheme,
          showUrlInput: true,
          showGaps: true,
        });
      } else {
        document.getElementById('provenanceViewer').innerHTML =
          '<div class="p-6 text-sm text-rose-500 bg-slate-900">Could not load @micropasts/provenance-timeline UMD bundle from unpkg.</div>';
      }
      updateProvenanceBadge(docsCache[activeId]);
    }

    function switchStageTab(tab) {
      const graphEl = document.getElementById('viewer');
      const provEl = document.getElementById('provenanceViewer');
      const btnGraph = document.getElementById('stageTabGraph');
      const btnProv = document.getElementById('stageTabProvenance');
      if (tab === 'graph') {
        graphEl.classList.remove('hidden');
        provEl.classList.add('hidden');
        btnGraph.classList.add('bg-white', 'dark:bg-slate-900', 'text-slate-900', 'dark:text-white', 'shadow-xs');
        btnGraph.classList.remove('text-slate-600', 'dark:text-slate-300');
        btnProv.classList.remove('bg-white', 'dark:bg-slate-900', 'text-slate-900', 'dark:text-white', 'shadow-xs');
        btnProv.classList.add('text-slate-600', 'dark:text-slate-300');
      } else {
        graphEl.classList.add('hidden');
        provEl.classList.remove('hidden');
        btnProv.classList.add('bg-white', 'dark:bg-slate-900', 'text-slate-900', 'dark:text-white', 'shadow-xs');
        btnProv.classList.remove('text-slate-600', 'dark:text-slate-300');
        btnGraph.classList.remove('bg-white', 'dark:bg-slate-900', 'text-slate-900', 'dark:text-white', 'shadow-xs');
        btnGraph.classList.add('text-slate-600', 'dark:text-slate-300');
      }
    }

    document.getElementById('stageTabGraph').addEventListener('click', () => switchStageTab('graph'));
    document.getElementById('stageTabProvenance').addEventListener('click', () => switchStageTab('provenance'));

    document.getElementById('toggleContextBtn').addEventListener('click', () => {
      contextVisible = !contextVisible;
      document.getElementById('contextStrip').classList.toggle('hidden', !contextVisible);
      document.getElementById('toggleContextBtn').textContent = contextVisible ? 'Hide Media & Map' : 'Show Media & Map';
      if (contextVisible && mapInstance) {
        setTimeout(() => mapInstance.resize(), 50);
      }
    });

    document.getElementById('themeToggle').addEventListener('click', () => {
      const isDark = document.documentElement.classList.toggle('dark');
      if (viewerInstance && typeof viewerInstance.setTheme === 'function') {
        viewerInstance.setTheme(isDark ? 'dark' : 'light');
      }
      if (provenanceInstance && typeof provenanceInstance.setTheme === 'function') {
        provenanceInstance.setTheme(isDark ? 'dark' : 'light');
      }
      if (mapInstance) {
        mapInstance.setStyle(isDark
          ? 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'
          : 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json');
      }
    });

