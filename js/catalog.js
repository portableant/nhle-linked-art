    function populateSelect(selectId, entries, defaultLabel) {
      const sel = document.getElementById(selectId);
      const current = sel.value;
      sel.innerHTML = `<option value="">${defaultLabel}</option>` +
        entries.map(([val, count]) => `<option value="${val.replace(/"/g, '&quot;')}">${val} (${count})</option>`).join('');
      if (current) sel.value = current;
    }

    function countField(key) {
      const counts = {};
      catalog.forEach(item => {
        const vals = Array.isArray(item[key]) ? item[key] : [item[key]];
        vals.filter(Boolean).forEach(v => {
          counts[v] = (counts[v] || 0) + 1;
        });
      });
      return Object.entries(counts).sort((a, b) => b[1] - a[1]);
    }

    function refreshDropdowns() {
      populateSelect('gradeSelect', countField('grade'), 'All Grades');
      populateSelect('placeSelect', countField('place'), 'All Localities');
      populateSelect('materialSelect', countField('materials'), 'All Materials (AAT)');
      populateSelect('architectSelect', countField('architects'), 'All Architects / Makers');
      populateSelect('periodSelect', countField('periods'), 'All Periods');
    }

    function getFiltered() {
      const q = state.q.toLowerCase();
      return catalog.filter(item => {
        if (state.grade && item.grade !== state.grade) return false;
        if (state.place && item.place !== state.place) return false;
        if (state.material && !(item.materials || []).includes(state.material)) return false;
        if (state.architect && !(item.architects || []).includes(state.architect)) return false;
        if (state.period && !(item.periods || []).includes(state.period)) return false;
        if (state.hasImage && !item.hasImage) return false;
        if (q) {
          const hay = `${item.id} ${item.name} ${item.place} ${item.ngr || ''} ${(item.architects || []).join(' ')}`.toLowerCase();
          if (!hay.includes(q)) return false;
        }
        return true;
      });
    }

    function hasActiveFilters() {
      return Boolean(state.q || state.grade || state.place || state.material || state.architect || state.period || state.hasImage);
    }

    function renderList() {
      const filtered = getFiltered();
      document.getElementById('resultCount').textContent = `${filtered.length} / ${catalog.length}`;
      document.getElementById('resetFilters').classList.toggle('hidden', !hasActiveFilters());

      const listEl = document.getElementById('assetList');
      const loadMoreBar = document.getElementById('loadMoreBar');

      if (!filtered.length) {
        listEl.innerHTML = `<div class="p-6 text-center text-xs text-slate-500">No matching assets.</div>`;
        loadMoreBar.classList.add('hidden');
        return;
      }

      const slice = filtered.slice(0, renderLimit);
      listEl.innerHTML = slice.map(item => {
        const selected = item.id === activeId;
        const rowCls = selected
          ? 'bg-sky-50/80 dark:bg-sky-950/40 border-l-2 border-l-sky-500'
          : 'hover:bg-slate-50 dark:hover:bg-slate-800/50';
        const imgDot = item.hasImage ? '<span title="Commons image available" class="w-1.5 h-1.5 rounded-full bg-rose-500 inline-block"></span>' : '';
        const wdTag = item.wikidataQid ? `<span class="text-[10px] font-mono text-indigo-400">${item.wikidataQid}</span>` : '';
        return `
          <button type="button" data-id="${item.id}" class="asset-card w-full text-left px-3.5 py-2.5 transition-colors block ${rowCls}">
            <div class="flex items-center justify-between gap-2">
              <span class="text-[11px] font-mono text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
                #${item.id} ${imgDot} ${wdTag}
              </span>
              <span class="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                ${item.grade === 'SM' ? 'SM' : 'Gr ' + item.grade}
              </span>
            </div>
            <div class="text-xs font-medium text-slate-900 dark:text-slate-100 truncate mt-0.5">${item.name}</div>
            <div class="text-[11px] text-slate-500 dark:text-slate-400 truncate">${item.place}</div>
          </button>
        `;
      }).join('');

      if (filtered.length > renderLimit) {
        loadMoreBar.classList.remove('hidden');
        document.getElementById('loadMoreBtn').textContent = `Show more (${filtered.length - renderLimit} remaining)`;
      } else {
        loadMoreBar.classList.add('hidden');
      }

      document.querySelectorAll('.asset-card').forEach(card => {
        card.addEventListener('click', () => selectAsset(card.dataset.id));
      });
    }

    document.getElementById('loadMoreBtn').addEventListener('click', () => {
      renderLimit += 100;
      renderList();
    });

