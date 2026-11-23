    // =========================================================================
    // Full Description Modal Overlay (`referred_to_by` + `identified_by`)
    // =========================================================================
    const descModal = document.getElementById('descriptionModal');

    function openDescriptionModal() {
      const doc = docsCache[activeId];
      if (!doc) return;

      const primaryName = (doc.identified_by || []).find(i => i.type === 'Name')?.content || doc._label;
      const gradeConcept = (doc.classified_as || []).find(c => c.id && c.id.includes('/concept/'));
      document.getElementById('descModalTitle').textContent = primaryName;
      document.getElementById('descModalGrade').textContent = gradeConcept ? gradeConcept._label.replace(' Listed Building', '') : 'Listed';
      document.getElementById('descModalMeta').textContent = `${doc.current_location?._label || ''} • NHLE #${activeId}`;

      // Identifiers (`identified_by`)
      const idContainer = document.getElementById('descModalIdentifiers');
      const ids = (doc.identified_by || []).filter(i => i.type === 'Identifier');
      idContainer.innerHTML = ids.length
        ? ids.map(i => {
            const kind = i.classified_as?.[0]?._label || 'Identifier';
            return `<span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 font-mono text-[11px]"><span class="text-slate-400">${kind}:</span> <strong class="text-slate-800 dark:text-slate-100">${i.content}</strong></span>`;
          }).join('')
        : '<span class="text-slate-400">No additional identifiers</span>';

      // Description sections (`referred_to_by`)
      const bodyEl = document.getElementById('descModalBody');
      const refs = doc.referred_to_by || [];
      if (refs.length) {
        bodyEl.innerHTML = refs.map(r => {
          const heading = r.classified_as?.[0]?._label || 'Official List Text';
          const paras = String(r.content || '')
            .split(/\n+/)
            .map(p => p.trim())
            .filter(Boolean)
            .map(p => `<p class="whitespace-pre-line">${p.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</p>`)
            .join('');
          return `
            <section class="space-y-2">
              <h3 class="text-xs font-semibold uppercase tracking-wider text-sky-700 dark:text-sky-400 border-b border-slate-100 dark:border-slate-800 pb-1">
                ${heading}
              </h3>
              <div class="space-y-2 text-slate-700 dark:text-slate-200">${paras}</div>
            </section>
          `;
        }).join('');
      } else {
        bodyEl.innerHTML = '<p class="text-slate-400 italic">No full-text description blocks are embedded in this Linked Art record. Use the Historic England link below to view the statutory entry.</p>';
      }

      const heUrl = (doc.subject_of || []).find(s => s.id && s.id.includes('historicengland.org.uk'))?.id
        || `https://historicengland.org.uk/listing/the-list/list-entry/${activeId}`;
      document.getElementById('descModalHeLink').href = heUrl;

      descModal.classList.remove('hidden');
      descModal.classList.add('flex');
    }

    function closeDescriptionModal() {
      descModal.classList.add('hidden');
      descModal.classList.remove('flex');
    }

    document.getElementById('openDescriptionBtn').addEventListener('click', openDescriptionModal);
    document.getElementById('dossierExpandBtn').addEventListener('click', openDescriptionModal);
    document.getElementById('closeDescModalBtn').addEventListener('click', closeDescriptionModal);
    document.getElementById('closeDescModalFooterBtn').addEventListener('click', closeDescriptionModal);
    descModal.addEventListener('click', (e) => {
      if (e.target === descModal) closeDescriptionModal();
    });

    document.getElementById('copyDescTextBtn').addEventListener('click', async () => {
      const doc = docsCache[activeId];
      if (!doc) return;
      const fullText = (doc.referred_to_by || [])
        .map(r => `${r.classified_as?.[0]?._label || 'Description'}:\n${r.content}`)
        .join('\n\n');
      if (!fullText) return;
      await navigator.clipboard.writeText(fullText);
      const btn = document.getElementById('copyDescTextBtn');
      btn.textContent = 'Copied!';
      setTimeout(() => btn.textContent = 'Copy Text', 1400);
    });

