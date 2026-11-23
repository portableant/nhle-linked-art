    let catalog = [...SEED_CATALOG];
    let docsCache = { ...SEED_DOCS };
    let activeId = catalog[0]?.id || '';
    let renderLimit = 100;
    let viewerInstance = null;
    let provenanceInstance = null;
    let mapInstance = null;
    let activeMarker = null;
    let contextVisible = true;

    const state = {
      q: '',
      grade: '',
      place: '',
      material: '',
      architect: '',
      period: '',
      hasImage: false,
    };

