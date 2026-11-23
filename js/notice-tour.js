    // =========================================================================
    // OGL v3.0 & Historic England Non-Endorsement Dismissible Modal
    // =========================================================================
    const OGL_STORAGE_KEY = 'nhle_linked_art_ogl_notice_dismissed_v1';
    const oglModal = document.getElementById('oglNoticeModal');

    function showOglModal() {
      oglModal.classList.remove('hidden');
      oglModal.classList.add('flex');
    }

    function hideOglModal(startTourAfter = false) {
      oglModal.classList.add('hidden');
      oglModal.classList.remove('flex');
      try {
        localStorage.setItem(OGL_STORAGE_KEY, '1');
      } catch (e) {}
      if (startTourAfter) {
        setTimeout(() => runGuidedTour(), 150);
      }
    }

    document.getElementById('dismissOglBtn').addEventListener('click', () => hideOglModal(false));
    document.getElementById('closeOglModalX').addEventListener('click', () => hideOglModal(false));
    document.getElementById('dismissAndTourBtn').addEventListener('click', () => hideOglModal(true));
    document.getElementById('openNoticeBtn').addEventListener('click', () => showOglModal());

    oglModal.addEventListener('click', (e) => {
      if (e.target === oglModal) hideOglModal(false);
    });

    // Show OGL v3 modal automatically on first visit unless already dismissed
    try {
      if (!localStorage.getItem(OGL_STORAGE_KEY)) {
        showOglModal();
      }
    } catch (e) {
      showOglModal();
    }

    // =========================================================================
    // Intro.js Guided Tour of the Linked Art Interface
    // =========================================================================
    function runGuidedTour() {
      if (typeof introJs !== 'function') return;

      // Ensure context panel is visible so all tour targets are on screen
      if (!contextVisible) {
        contextVisible = true;
        document.getElementById('contextStrip').classList.remove('hidden');
        document.getElementById('toggleContextBtn').textContent = 'Hide Media & Map';
        if (mapInstance) setTimeout(() => mapInstance.resize(), 50);
      }

      const tour = introJs();
      tour.setOptions({
        showProgress: true,
        showBullets: false,
        exitOnOverlayClick: true,
        nextLabel: 'Next &rarr;',
        prevLabel: '&larr; Back',
        doneLabel: 'Finish Tour',
        steps: [
          {
            title: 'NHLE Linked Art 1.0 Explorer',
            intro: 'Welcome! This interface transforms Historic England National Heritage List for England (NHLE) records into Linked Art v1.0 JSON-LD knowledge graphs.'
          },
          {
            element: '#filterToolbar',
            title: 'Faceted Search & Filtering',
            intro: 'Search by building name, NGR, or architect, or filter across Statutory Grade, Locality, Getty AAT Materials, Historical Period, and records with Wikimedia Commons photos.'
          },
          {
            element: '#assetSidebar',
            title: 'HumanMadeObject Catalog',
            intro: 'Browse matching heritage assets here. Selecting any record updates the browser URL (?id=...) so you can bookmark or share direct links.'
          },
          {
            element: '#activeHeaderCard',
            title: 'Outbound Links & JSON-LD Export',
            intro: 'Jump straight to the official Historic England listing, exact-match Wikidata QID, Wikipedia, or OpenStreetMap, or copy/download the raw Linked Art JSON-LD document.'
          },
          {
            element: '#contextStrip',
            title: 'Media, Spatial Place & Lifecycle Timeline',
            intro: 'Inspect Wikimedia Commons photography, WGS84/OSGB36 map coordinates, Getty AAT material tags, and a chronological timeline of construction, alteration, and statutory listing events.'
          },
          {
            element: '#inspectorStage',
            title: 'Interactive Linked Art Graph & Inspector',
            intro: 'Switch between the force-directed D3 semantic network graph (@micropasts/linked-art-viewer) and the vertical Chain of Custody & Provenance Timeline (@micropasts/provenance-timeline) with automatic gap detection.'
          },
          {
            element: '#openCorpusBtn',
            title: 'Corpus Visualisations (Matrix & Overview Map)',
            intro: 'Open the Corpus Explorer to inspect a Getty AAT Material × Period heatmap matrix and an interactive spatial map of all monuments.'
          },
          {
            element: '#lookupForm',
            title: 'Live NHLE ID Resolver',
            intro: 'Enter any NHLE List Entry Number (such as 1083558 or 1124892) to resolve local shards or fetch live metadata from Historic England and Wikidata.'
          }
        ]
      });
      tour.start();
    }

    document.getElementById('startTourBtn').addEventListener('click', () => runGuidedTour());

