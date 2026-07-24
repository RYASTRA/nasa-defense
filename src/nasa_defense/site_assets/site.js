(() => {
  "use strict";

  const DEFAULT_PAGE_SIZE = 18;
  const DIALOG_HISTORY_KEY = "nasaDefenseRiskDialog";
  const FILTER_PARAMS = ["q", "scope", "sort", "page", "object"];
  const SCOPES = new Set(["watch", "all", "torino", "palermo", "probability", "size"]);
  const SORTS = new Set(["attention", "probability", "size", "observed", "name"]);
  const SIGNALS = new Set(["torino", "palermo", "probability", "size"]);
  const signalOrder = ["torino", "palermo", "probability", "size"];
  const designationCollator = new Intl.Collator("en", {
    numeric: true,
    sensitivity: "base",
  });
  const numberFormatter = new Intl.NumberFormat("en", {
    maximumSignificantDigits: 4,
  });
  const integerFormatter = new Intl.NumberFormat("en", {
    maximumFractionDigits: 0,
  });
  const dateFormatter = new Intl.DateTimeFormat("en", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  const controls = document.querySelector("#risk-controls");
  const searchInput = document.querySelector("#risk-search");
  const scopeSelect = document.querySelector("#risk-scope");
  const sortSelect = document.querySelector("#risk-sort");
  const resetButton = document.querySelector("#risk-clear");
  const loadingMessage = document.querySelector("#risk-loading");
  const errorMessage = document.querySelector("#risk-error");
  const statusMessage = document.querySelector("#risk-status");
  const resultsContainer = document.querySelector("#risk-results");
  const pagination = document.querySelector("#risk-pagination");
  const dialog = document.querySelector("#risk-dialog");
  const dialogContent = document.querySelector("#risk-dialog-content");
  const dialogCloseButton = document.querySelector("#risk-dialog-close");

  let catalog = [];
  let filteredCatalog = [];
  let lastDialogTrigger = null;
  let lastDialogDesignation = "";
  let pageSize = DEFAULT_PAGE_SIZE;
  let thresholds = {
    palermo: -3,
    probability: 0.0001,
    diameterM: 140,
  };
  let viewState = readUrlState();

  initApophisCountdown();

  if (
    !controls ||
    !searchInput ||
    !scopeSelect ||
    !sortSelect ||
    !resetButton ||
    !loadingMessage ||
    !errorMessage ||
    !statusMessage ||
    !resultsContainer ||
    !pagination ||
    !dialog ||
    !dialogContent ||
    !dialogCloseButton
  ) {
    return;
  }

  bindEvents();
  applyStateToControls();
  syncUrl("replace");
  setControlsDisabled(true);
  resultsContainer.setAttribute("aria-busy", "true");
  void loadCatalog();

  function element(tagName, className, text) {
    const node = document.createElement(tagName);
    if (className) {
      node.className = className;
    }
    if (text !== undefined && text !== null) {
      node.textContent = String(text);
    }
    return node;
  }

  function finiteNumber(value) {
    return typeof value === "number" && Number.isFinite(value) ? value : null;
  }

  function normalizedText(value, maximumLength = 120) {
    return typeof value === "string" ? value.trim().slice(0, maximumLength) : "";
  }

  function folded(value) {
    return String(value).normalize("NFKC").toLocaleLowerCase("en");
  }

  function readUrlState() {
    const parameters = new URL(window.location.href).searchParams;
    const scope = parameters.get("scope") || "watch";
    const sort = parameters.get("sort") || "attention";
    const parsedPage = Number.parseInt(parameters.get("page") || "1", 10);
    return {
      query: normalizedText(parameters.get("q") || "", 100),
      scope: SCOPES.has(scope) ? scope : "watch",
      sort: SORTS.has(sort) ? sort : "attention",
      page: Number.isSafeInteger(parsedPage) && parsedPage > 0 ? parsedPage : 1,
      object: normalizedText(parameters.get("object") || "", 120),
    };
  }

  function applyStateToControls() {
    searchInput.value = viewState.query;
    scopeSelect.value = viewState.scope;
    sortSelect.value = viewState.sort;
  }

  function syncUrl(mode, options = {}) {
    const url = new URL(window.location.href);
    for (const parameter of FILTER_PARAMS) {
      url.searchParams.delete(parameter);
    }

    if (viewState.query) {
      url.searchParams.set("q", viewState.query);
    }
    if (viewState.scope !== "watch") {
      url.searchParams.set("scope", viewState.scope);
    }
    if (viewState.sort !== "attention") {
      url.searchParams.set("sort", viewState.sort);
    }
    if (viewState.page > 1) {
      url.searchParams.set("page", String(viewState.page));
    }
    if (viewState.object) {
      url.searchParams.set("object", viewState.object);
    }

    const nextHistoryState = { ...(window.history.state || {}) };
    if (options.dialogEntry) {
      nextHistoryState[DIALOG_HISTORY_KEY] = true;
    } else if (!viewState.object) {
      delete nextHistoryState[DIALOG_HISTORY_KEY];
    } else if (!window.history.state?.[DIALOG_HISTORY_KEY]) {
      delete nextHistoryState[DIALOG_HISTORY_KEY];
    }

    if (mode === "push") {
      window.history.pushState(nextHistoryState, "", url);
    } else {
      window.history.replaceState(nextHistoryState, "", url);
    }
  }

  function bindEvents() {
    controls.addEventListener("submit", (event) => {
      event.preventDefault();
    });

    searchInput.addEventListener("input", () => {
      viewState.query = normalizedText(searchInput.value, 100);
      viewState.page = 1;
      syncUrl("replace");
      renderResults();
    });

    scopeSelect.addEventListener("change", () => {
      viewState.scope = SCOPES.has(scopeSelect.value) ? scopeSelect.value : "watch";
      viewState.page = 1;
      syncUrl("replace");
      renderResults();
    });

    sortSelect.addEventListener("change", () => {
      viewState.sort = SORTS.has(sortSelect.value) ? sortSelect.value : "attention";
      viewState.page = 1;
      syncUrl("replace");
      renderResults();
    });

    resetButton.addEventListener("click", () => {
      viewState = {
        query: "",
        scope: "watch",
        sort: "attention",
        page: 1,
        object: "",
      };
      applyStateToControls();
      syncUrl("replace");
      renderResults();
      searchInput.focus();
    });

    dialogCloseButton.addEventListener("click", requestDialogClose);

    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      requestDialogClose();
    });

    dialog.addEventListener("click", (event) => {
      if (event.target !== dialog) {
        return;
      }
      const bounds = dialog.getBoundingClientRect();
      const insideDialog =
        event.clientX >= bounds.left &&
        event.clientX <= bounds.right &&
        event.clientY >= bounds.top &&
        event.clientY <= bounds.bottom;
      if (!insideDialog) {
        requestDialogClose();
      }
    });

    dialog.addEventListener("close", () => {
      if (viewState.object) {
        viewState.object = "";
        syncUrl("replace");
      }
      restoreDialogFocus();
    });

    window.addEventListener("popstate", () => {
      viewState = readUrlState();
      applyStateToControls();
      renderResults();
      reconcileDialogFromUrl({ announceMissing: true });
    });
  }

  function setControlsDisabled(disabled) {
    for (const control of controls.elements) {
      control.disabled = disabled;
    }
  }

  async function loadCatalog() {
    loadingMessage.hidden = false;
    errorMessage.hidden = true;

    try {
      const response = await window.fetch("data/sentry.json", {
        cache: "no-cache",
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        throw new Error(`Catalog request returned ${response.status}`);
      }

      const documentValue = await response.json();
      if (
        !documentValue ||
        typeof documentValue !== "object" ||
        !Array.isArray(documentValue.objects)
      ) {
        throw new Error("Catalog response has an unexpected shape");
      }

      thresholds = normalizeThresholds(documentValue.thresholds);
      pageSize =
        Number.isSafeInteger(documentValue.results_per_page) &&
        documentValue.results_per_page >= 1 &&
        documentValue.results_per_page <= 100
          ? documentValue.results_per_page
          : DEFAULT_PAGE_SIZE;
      const records = documentValue.objects
        .map(normalizeRecord)
        .filter((record) => record !== null);
      catalog = deduplicateRecords(records);

      loadingMessage.hidden = true;
      resultsContainer.setAttribute("aria-busy", "false");
      setControlsDisabled(false);
      renderResults();
      reconcileDialogFromUrl({ announceMissing: true });
    } catch (error) {
      showCatalogError();
    }
  }

  function normalizeThresholds(rawThresholds) {
    const raw =
      rawThresholds && typeof rawThresholds === "object" ? rawThresholds : {};
    return {
      palermo:
        finiteNumber(raw.palermo_floor) === null ? -3 : raw.palermo_floor,
      probability:
        finiteNumber(raw.impact_probability_floor) === null
          ? 0.0001
          : raw.impact_probability_floor,
      diameterM:
        finiteNumber(raw.diameter_floor_m) === null ? 140 : raw.diameter_floor_m,
    };
  }

  function normalizeRecord(rawRecord) {
    if (!rawRecord || typeof rawRecord !== "object") {
      return null;
    }
    const designation = normalizedText(rawRecord.des, 120);
    if (!designation) {
      return null;
    }

    const record = {
      des: designation,
      diameterKm: finiteNumber(rawRecord.diameter_km),
      torino: Math.max(0, Math.trunc(finiteNumber(rawRecord.ts_max) || 0)),
      palermo: finiteNumber(rawRecord.ps_cum),
      probability: Math.max(0, finiteNumber(rawRecord.ip) || 0),
      lastObservation: normalizedText(rawRecord.last_obs, 80),
      noteworthy: rawRecord.noteworthy === true,
      signals: Array.isArray(rawRecord.signals)
        ? rawRecord.signals.filter((signal) => SIGNALS.has(signal))
        : [],
    };

    if (record.signals.length === 0 && record.noteworthy) {
      record.signals = deriveSignals(record);
    }
    record.signals = signalOrder.filter((signal) => record.signals.includes(signal));
    return record;
  }

  function deriveSignals(record) {
    const signals = [];
    if (record.torino >= 1) {
      signals.push("torino");
    }
    if (
      record.palermo !== null &&
      record.palermo > -90 &&
      record.palermo >= thresholds.palermo
    ) {
      signals.push("palermo");
    }
    if (record.probability >= thresholds.probability) {
      signals.push("probability");
    }
    if (
      record.diameterKm !== null &&
      record.diameterKm * 1000 >= thresholds.diameterM
    ) {
      signals.push("size");
    }
    return signals;
  }

  function deduplicateRecords(records) {
    const byDesignation = new Map();
    for (const record of records) {
      const key = folded(record.des);
      if (!byDesignation.has(key)) {
        byDesignation.set(key, record);
      }
    }
    return [...byDesignation.values()];
  }

  function showCatalogError() {
    loadingMessage.hidden = true;
    resultsContainer.setAttribute("aria-busy", "false");
    resultsContainer.replaceChildren();
    pagination.replaceChildren();
    pagination.hidden = true;
    statusMessage.textContent = "The interactive Sentry catalog is unavailable.";

    const title = element("strong", "", "The catalog could not be loaded.");
    const explanation = element(
      "p",
      "",
      "The rest of the dashboard is still available. Reload the page or open the machine-readable snapshot directly.",
    );
    const dataLink = element("a", "", "Open the Sentry JSON");
    dataLink.href = "data/sentry.json";
    errorMessage.replaceChildren(title, explanation, dataLink);
    errorMessage.hidden = false;
  }

  function scopeMatches(record) {
    switch (viewState.scope) {
      case "all":
        return true;
      case "torino":
        return record.torino >= 1;
      case "palermo":
        return record.signals.includes("palermo");
      case "probability":
        return record.signals.includes("probability");
      case "size":
        return record.signals.includes("size");
      case "watch":
      default:
        return record.noteworthy || record.signals.length > 0;
    }
  }

  function compareNullableDescending(left, right, unavailableFloor = -Infinity) {
    const leftValue = left === null ? unavailableFloor : left;
    const rightValue = right === null ? unavailableFloor : right;
    return rightValue - leftValue;
  }

  function compareAttention(left, right) {
    return (
      right.torino - left.torino ||
      compareNullableDescending(left.palermo, right.palermo, -Infinity) ||
      right.probability - left.probability ||
      compareNullableDescending(left.diameterKm, right.diameterKm) ||
      designationCollator.compare(left.des, right.des)
    );
  }

  function compareRecords(left, right) {
    switch (viewState.sort) {
      case "probability":
        return right.probability - left.probability || compareAttention(left, right);
      case "size":
        return (
          compareNullableDescending(left.diameterKm, right.diameterKm) ||
          compareAttention(left, right)
        );
      case "observed":
        return (
          observationTimestamp(right.lastObservation) -
            observationTimestamp(left.lastObservation) ||
          compareAttention(left, right)
        );
      case "name":
        return designationCollator.compare(left.des, right.des);
      case "attention":
      default:
        return compareAttention(left, right);
    }
  }

  function renderResults(options = {}) {
    const query = folded(viewState.query);
    filteredCatalog = catalog
      .filter((record) => scopeMatches(record))
      .filter((record) => !query || folded(record.des).includes(query))
      .sort(compareRecords);

    const pageCount = Math.max(1, Math.ceil(filteredCatalog.length / pageSize));
    const correctedPage = Math.min(Math.max(1, viewState.page), pageCount);
    if (correctedPage !== viewState.page) {
      viewState.page = correctedPage;
      syncUrl("replace");
    }

    resultsContainer.replaceChildren();
    if (filteredCatalog.length === 0) {
      resultsContainer.append(buildEmptyState());
      pagination.replaceChildren();
      pagination.hidden = true;
      statusMessage.textContent = emptyStatusText();
      return;
    }

    const firstIndex = (viewState.page - 1) * pageSize;
    const visibleRecords = filteredCatalog.slice(firstIndex, firstIndex + pageSize);
    const fragment = document.createDocumentFragment();
    visibleRecords.forEach((record, index) => {
      fragment.append(buildRiskCard(record, firstIndex + index));
    });
    resultsContainer.append(fragment);
    renderPagination(pageCount);
    statusMessage.textContent = resultStatusText(
      firstIndex + 1,
      firstIndex + visibleRecords.length,
      filteredCatalog.length,
      pageCount,
    );

    if (options.focusStatus) {
      focusAndScrollToResults();
    }
  }

  function buildEmptyState() {
    const empty = element("div", "empty-state");
    const title = element("strong", "", "No matching objects.");
    const copy = element(
      "p",
      "",
      viewState.query
        ? `No designation in this view contains “${viewState.query}”. Try a shorter search or reset the filters.`
        : "No objects meet this attention rule in the current Sentry snapshot.",
    );
    empty.append(title, copy);
    return empty;
  }

  function scopeLabel() {
    const labels = {
      watch: "watch signals",
      all: "catalog objects",
      torino: "objects at Torino 1 or higher",
      palermo: "objects meeting the Palermo floor",
      probability: "objects meeting the probability floor",
      size: "objects meeting the size floor",
    };
    return labels[viewState.scope] || labels.watch;
  }

  function emptyStatusText() {
    const searchSuffix = viewState.query ? ` for “${viewState.query}”` : "";
    return `No ${scopeLabel()} match${searchSuffix}.`;
  }

  function resultStatusText(first, last, total, pageCount) {
    const searchSuffix = viewState.query ? ` matching “${viewState.query}”` : "";
    const pageSuffix = pageCount > 1 ? ` Page ${viewState.page} of ${pageCount}.` : "";
    return `Showing ${first}–${last} of ${integerFormatter.format(total)} ${scopeLabel()}${searchSuffix}.${pageSuffix}`;
  }

  function buildRiskCard(record, absoluteIndex) {
    const card = element("article", "risk-card");
    const headingId = `risk-object-${absoluteIndex + 1}`;
    card.setAttribute("aria-labelledby", headingId);

    const header = element("div", "risk-card__header");
    const heading = element("h3");
    heading.id = headingId;
    const identity = element("a", "risk-card__designation", record.des);
    identity.href = objectDeepLink(record.des);
    identity.dataset.designation = record.des;
    identity.setAttribute("aria-label", `Inspect Sentry details for ${record.des}`);
    identity.addEventListener("click", (event) => {
      if (
        event.button !== 0 ||
        event.metaKey ||
        event.ctrlKey ||
        event.shiftKey ||
        event.altKey
      ) {
        return;
      }
      event.preventDefault();
      openRecord(record, identity);
    });
    heading.append(identity);
    header.append(heading, buildSignalBadges(record, "risk-card__badges"));

    const facts = element("dl", "risk-facts");
    appendFact(facts, "Approx. diameter", formatDiameter(record.diameterKm), "CNEOS estimate");
    appendFact(facts, "Torino scale", `${record.torino} / 10`, "public-communication scale");
    appendFact(
      facts,
      "Palermo (cumulative)",
      formatPalermo(record.palermo),
      "0 equals background hazard",
    );
    appendFact(
      facts,
      "Cumulative probability",
      formatProbabilityPercent(record.probability),
      "modeled impact solutions",
    );

    const context = element("div", "risk-card__context");
    context.append(
      element("p", "", watchContext(record)),
      element(
        "small",
        "",
        `Last observation: ${formatObservation(record.lastObservation)}`,
      ),
    );

    card.append(header, facts, context);
    return card;
  }

  function appendFact(list, label, value, note) {
    const row = element("div");
    const term = element("dt", "", label);
    const description = element("dd");
    description.append(document.createTextNode(value));
    if (note) {
      description.title = note;
      description.setAttribute("aria-label", `${value}; ${note}`);
    }
    row.append(term, description);
    list.append(row);
  }

  function buildSignalBadges(record, containerClass) {
    const container = element("div", containerClass);
    if (record.signals.length === 0) {
      const quiet = element(
        "span",
        "signal-badge signal-badge--quiet",
        "Below watch rules",
      );
      quiet.title = "This object is in Sentry but does not cross a current attention floor";
      container.append(quiet);
      return container;
    }

    const badgeDetails = {
      torino: {
        className: "signal-badge--torino",
        label: `Torino ${record.torino}`,
        title: "The public-communication rating is above zero",
      },
      palermo: {
        className: "signal-badge--palermo",
        label: `Palermo ${formatPalermo(record.palermo)}`,
        title: `The cumulative Palermo value meets the ${formatPalermo(thresholds.palermo)} watch floor`,
      },
      probability: {
        className: "signal-badge--probability",
        label: "Probability watch",
        title: `Cumulative probability meets the ${formatScientific(thresholds.probability)} watch floor`,
      },
      size: {
        className: "signal-badge--size",
        label: "Size watch",
        title: `Estimated diameter is at least ${integerFormatter.format(thresholds.diameterM)} m`,
      },
    };

    for (const signal of record.signals) {
      const detail = badgeDetails[signal];
      if (!detail) {
        continue;
      }
      const badge = element(
        "span",
        `signal-badge ${detail.className}`,
        detail.label,
      );
      badge.title = detail.title;
      container.append(badge);
    }
    return container;
  }

  function watchContext(record) {
    if (record.torino >= 1) {
      return `Torino ${record.torino} merits public attention and follow-up. It is not, by itself, an impact prediction.`;
    }
    if (record.signals.length === 0) {
      return "This catalog object is below the watcher’s current attention floors.";
    }
    const signalNames = record.signals.map((signal) => {
      const labels = {
        torino: "Torino",
        palermo: "Palermo",
        probability: "probability",
        size: "size",
      };
      return labels[signal];
    });
    return `Flagged by the ${formatList(signalNames)} attention rule${signalNames.length === 1 ? "" : "s"}. A watch signal is context for review, not a forecast.`;
  }

  function formatList(values) {
    if (typeof Intl.ListFormat === "function") {
      return new Intl.ListFormat("en", {
        style: "long",
        type: "conjunction",
      }).format(values);
    }
    if (values.length < 2) {
      return values[0] || "";
    }
    return `${values.slice(0, -1).join(", ")} and ${values.at(-1)}`;
  }

  function renderPagination(pageCount) {
    pagination.replaceChildren();
    pagination.hidden = pageCount <= 1;
    if (pageCount <= 1) {
      return;
    }

    pagination.append(
      paginationButton("← Previous", viewState.page - 1, {
        disabled: viewState.page === 1,
        label: "Go to the previous result page",
      }),
    );

    for (const token of paginationTokens(viewState.page, pageCount)) {
      if (token === null) {
        const ellipsis = element("span", "pagination-ellipsis", "…");
        ellipsis.setAttribute("aria-hidden", "true");
        pagination.append(ellipsis);
        continue;
      }
      pagination.append(
        paginationButton(String(token), token, {
          current: token === viewState.page,
          label:
            token === viewState.page
              ? `Current page, page ${token}`
              : `Go to result page ${token}`,
        }),
      );
    }

    pagination.append(
      paginationButton("Next →", viewState.page + 1, {
        disabled: viewState.page === pageCount,
        label: "Go to the next result page",
      }),
    );
  }

  function paginationTokens(currentPage, pageCount) {
    if (pageCount <= 7) {
      return Array.from({ length: pageCount }, (_, index) => index + 1);
    }

    const pages = new Set([1, pageCount, currentPage - 1, currentPage, currentPage + 1]);
    if (currentPage <= 4) {
      [2, 3, 4, 5].forEach((page) => pages.add(page));
    }
    if (currentPage >= pageCount - 3) {
      [pageCount - 4, pageCount - 3, pageCount - 2, pageCount - 1].forEach((page) =>
        pages.add(page),
      );
    }

    const validPages = [...pages]
      .filter((page) => page >= 1 && page <= pageCount)
      .sort((left, right) => left - right);
    const tokens = [];
    validPages.forEach((page, index) => {
      if (index > 0 && page - validPages[index - 1] > 1) {
        tokens.push(null);
      }
      tokens.push(page);
    });
    return tokens;
  }

  function paginationButton(text, targetPage, options = {}) {
    const button = element("button", "", text);
    button.type = "button";
    button.disabled = options.disabled === true || options.current === true;
    button.setAttribute("aria-label", options.label || text);
    if (options.current) {
      button.setAttribute("aria-current", "page");
    }
    if (!button.disabled) {
      button.addEventListener("click", () => {
        viewState.page = targetPage;
        syncUrl("push");
        renderResults({ focusStatus: true });
      });
    }
    return button;
  }

  function focusAndScrollToResults() {
    window.requestAnimationFrame(() => {
      resultsContainer.scrollIntoView({
        behavior: reducedMotion.matches ? "auto" : "smooth",
        block: "start",
      });
      try {
        statusMessage.focus({ preventScroll: true });
      } catch (error) {
        statusMessage.focus();
      }
    });
  }

  function openRecord(record, trigger) {
    lastDialogTrigger = trigger;
    lastDialogDesignation = record.des;
    viewState.object = record.des;
    syncUrl("push", { dialogEntry: true });
    showDialog(record);
  }

  function reconcileDialogFromUrl(options = {}) {
    if (!viewState.object) {
      closeDialog();
      return;
    }

    const requestedObject = folded(viewState.object);
    const record = catalog.find((candidate) => folded(candidate.des) === requestedObject);
    if (!record) {
      const missingObject = viewState.object;
      viewState.object = "";
      syncUrl("replace");
      closeDialog();
      if (options.announceMissing) {
        statusMessage.textContent = `Object “${missingObject}” is not present in the current Sentry catalog. ${statusMessage.textContent}`;
        window.requestAnimationFrame(() => {
          statusMessage.scrollIntoView({
            behavior: reducedMotion.matches ? "auto" : "smooth",
            block: "center",
          });
          statusMessage.focus();
        });
      }
      return;
    }

    if (record.des !== viewState.object) {
      viewState.object = record.des;
      syncUrl("replace");
    }
    showDialog(record);
  }

  function showDialog(record) {
    dialogContent.replaceChildren(buildDialogDetails(record));
    if (!dialog.open) {
      if (typeof dialog.showModal === "function") {
        dialog.showModal();
      } else {
        dialog.setAttribute("open", "");
      }
    }
    window.requestAnimationFrame(() => {
      try {
        dialogCloseButton.focus({ preventScroll: true });
      } catch (error) {
        dialogCloseButton.focus();
      }
    });
  }

  function buildDialogDetails(record) {
    const wrapper = document.createDocumentFragment();
    const header = element("div", "risk-detail__header");
    const identity = element("div", "risk-detail__identity");
    identity.append(
      element("p", "eyebrow", "CNEOS Sentry object"),
      element("h2", "", record.des),
      element(
        "p",
        "",
        `Last observation: ${formatObservation(record.lastObservation)}`,
      ),
    );
    identity.querySelector("h2").id = "risk-dialog-title";
    header.append(identity, buildSignalBadges(record, "risk-detail__badges"));

    const details = element("dl", "detail-grid");
    appendFact(details, "Approx. diameter", formatDiameter(record.diameterKm), "CNEOS estimate");
    appendFact(details, "Torino scale", `${record.torino} / 10`, torinoMeaning(record.torino));
    appendFact(
      details,
      "Palermo (cumulative)",
      formatPalermo(record.palermo),
      palermoMeaning(record.palermo),
    );
    appendFact(
      details,
      "Cumulative probability",
      formatProbabilityPercent(record.probability),
      `${formatScientific(record.probability)} as a fraction`,
    );

    const explainer = element("div", "detail-explainer");
    explainer.append(
      element("h3", "", "How to read this"),
      element("p", "", detailedContext(record)),
      element(
        "p",
        "",
        "Sentry probabilities are cumulative across modeled impact solutions and dates. They are not annual odds, and probability alone does not describe consequence.",
      ),
    );

    const actions = element("div", "dialog-actions");
    const officialLink = element("a", "button button--primary", "Open the official JPL record ↗");
    officialLink.href = officialRecordUrl(record.des);
    officialLink.rel = "external";
    const closeButton = element("button", "button", "Close");
    closeButton.type = "button";
    closeButton.addEventListener("click", requestDialogClose);
    actions.append(officialLink, closeButton);

    wrapper.append(header, details, explainer, actions);
    return wrapper;
  }

  function detailedContext(record) {
    const torinoText =
      record.torino === 0
        ? "Torino 0 means no unusual level of public concern."
        : `Torino ${record.torino} is above zero and should be followed through official updates.`;
    let palermoText = "No cumulative Palermo value is published.";
    if (record.palermo !== null && record.palermo > -90) {
      palermoText =
        record.palermo < 0
          ? `Its Palermo value (${formatPalermo(record.palermo)}) remains below the ordinary background hazard.`
          : `Its Palermo value (${formatPalermo(record.palermo)}) is at or above the ordinary background hazard.`;
    }
    return `${torinoText} ${palermoText} Diameter and probability still need to be read together.`;
  }

  function torinoMeaning(value) {
    return value === 0 ? "no unusual public concern" : "follow official updates";
  }

  function palermoMeaning(value) {
    if (value === null || value <= -90) {
      return "not published";
    }
    if (value < 0) {
      return "below background hazard";
    }
    if (value === 0) {
      return "equal to background hazard";
    }
    return "above background hazard";
  }

  function requestDialogClose() {
    if (!dialog.open && !dialog.hasAttribute("open")) {
      return;
    }
    if (viewState.object && window.history.state?.[DIALOG_HISTORY_KEY]) {
      window.history.back();
      return;
    }
    viewState.object = "";
    syncUrl("replace");
    closeDialog();
  }

  function closeDialog() {
    if (dialog.open && typeof dialog.close === "function") {
      dialog.close();
    } else if (dialog.hasAttribute("open")) {
      dialog.removeAttribute("open");
      restoreDialogFocus();
    }
  }

  function restoreDialogFocus() {
    let focusTarget = lastDialogTrigger?.isConnected ? lastDialogTrigger : null;
    if (!focusTarget && lastDialogDesignation) {
      focusTarget = [...resultsContainer.querySelectorAll(".risk-card__designation")].find(
        (candidate) => candidate.dataset.designation === lastDialogDesignation,
      );
    }
    if (!focusTarget && lastDialogDesignation) {
      focusTarget = statusMessage;
    }
    if (focusTarget) {
      try {
        focusTarget.focus({ preventScroll: true });
      } catch (error) {
        focusTarget.focus();
      }
    }
    lastDialogTrigger = null;
    lastDialogDesignation = "";
  }

  function officialRecordUrl(designation) {
    return `https://cneos.jpl.nasa.gov/sentry/details.html#?des=${encodeURIComponent(designation)}`;
  }

  function objectDeepLink(designation) {
    const url = new URL(window.location.href);
    url.searchParams.set("object", designation);
    return url.href;
  }

  function formatDiameter(diameterKm) {
    if (diameterKm === null || diameterKm < 0) {
      return "Not published";
    }
    if (diameterKm >= 1) {
      return `~${numberFormatter.format(diameterKm)} km`;
    }
    return `~${numberFormatter.format(diameterKm * 1000)} m`;
  }

  function formatPalermo(value) {
    if (value === null || value <= -90) {
      return "Not published";
    }
    return value.toFixed(2);
  }

  function formatProbabilityPercent(probability) {
    if (probability <= 0) {
      return "0%";
    }
    const percentage = probability * 100;
    if (percentage >= 0.001) {
      return `${numberFormatter.format(percentage)}%`;
    }
    return `${formatScientific(percentage)}%`;
  }

  function formatScientific(value) {
    if (value === null || !Number.isFinite(value)) {
      return "Not published";
    }
    if (value === 0) {
      return "0";
    }
    const [coefficient, exponent] = value.toExponential(2).split("e");
    return `${coefficient} × 10${toSuperscript(Number(exponent))}`;
  }

  function toSuperscript(value) {
    const characters = {
      "-": "−",
      "0": "⁰",
      "1": "¹",
      "2": "²",
      "3": "³",
      "4": "⁴",
      "5": "⁵",
      "6": "⁶",
      "7": "⁷",
      "8": "⁸",
      "9": "⁹",
    };
    return String(value)
      .split("")
      .map((character) => characters[character] || character)
      .join("");
  }

  function observationParts(rawValue) {
    const match = /^(\d{4})-(\d{1,2})-(\d{1,2}(?:\.\d+)?)/.exec(rawValue || "");
    if (!match) {
      return null;
    }
    const year = Number(match[1]);
    const month = Number(match[2]);
    const dayWithFraction = Number(match[3]);
    const day = Math.floor(dayWithFraction);
    if (
      !Number.isInteger(year) ||
      !Number.isInteger(month) ||
      !Number.isInteger(day) ||
      month < 1 ||
      month > 12 ||
      day < 1 ||
      day > 31
    ) {
      return null;
    }
    const timestamp =
      Date.UTC(year, month - 1, day) + (dayWithFraction - day) * 24 * 60 * 60 * 1000;
    const dateValue = new Date(timestamp);
    if (
      dateValue.getUTCFullYear() !== year ||
      dateValue.getUTCMonth() !== month - 1 ||
      dateValue.getUTCDate() !== day
    ) {
      return null;
    }
    return { date: dateValue, timestamp };
  }

  function observationTimestamp(value) {
    return observationParts(value)?.timestamp ?? -Infinity;
  }

  function formatObservation(value) {
    const parsed = observationParts(value);
    return parsed ? dateFormatter.format(parsed.date) : value || "Not published";
  }

  function initApophisCountdown() {
    const card = document.querySelector("[data-apophis-date]");
    const output = document.querySelector("#apophis-days");
    if (!card || !output) {
      return;
    }
    const dateValue = card.getAttribute("data-apophis-date") || "";
    const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateValue);
    if (!match) {
      return;
    }

    const target = Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
    if (!Number.isFinite(target)) {
      return;
    }
    const caption = output.nextElementSibling;

    const updateCountdown = () => {
      const now = new Date();
      const today = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate());
      const days = Math.round((target - today) / 86_400_000);
      output.textContent = integerFormatter.format(Math.abs(days));
      if (caption) {
        caption.textContent =
          days < 0 ? "days since closest approach" : "days to closest approach";
      }
    };

    updateCountdown();
    const now = new Date();
    const nextUtcMidnight =
      Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1) + 1000;
    window.setTimeout(() => {
      updateCountdown();
      window.setInterval(updateCountdown, 86_400_000);
    }, Math.max(1000, nextUtcMidnight - Date.now()));
  }
})();
