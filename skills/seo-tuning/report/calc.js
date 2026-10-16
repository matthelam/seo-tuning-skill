// All report arithmetic, from raw seo-jev responses. Pure functions, no DOM.
// Shared by the report page and (later) the terminal summary so both always agree.
(function (root) {
  const score = (result, kind) => result?.scores?.[kind]?.score ?? null
  const fit = (result, kind) => result?.scores?.[kind]?.intentFit ?? null
  const fidelity = (result) => {
    const m = score(result, 'meta'), p = score(result, 'page')
    return m != null && p ? m / p : null
  }
  const ratings = (result, kind) => result?.scores?.[kind]?.ratings ?? {}
  const covered = (result, keywords, threshold = 0.5) =>
    keywords.filter((k) => (ratings(result, 'page')[k.term] ?? 0) >= threshold).length
  const ceiling = (result, keywords) =>
    keywords.reduce((s, k) => s + (ratings(result, 'page')[k.term] ?? 0), 0)

  // A trial is either a raw test_revision result or a stored summary; both carry comparison.scores.
  const trialRows = (trial) => {
    const cmp = (trial.result ?? trial)?.comparison?.scores ?? {}
    return Object.entries(cmp).map(([metric, v]) => ({
      metric, before: v.before, after: v.after, delta: v.delta, verdict: v.verdict,
    }))
  }
  const trialError = (trial) => (trial.result ?? trial)?.error ?? null

  // The live result in force at each pass: a pass without a live measurement carries the last one.
  const liveSeries = (passes) => {
    let last = null
    return passes.map((p) => (last = p.live ?? last))
  }

  root.ReportCalc = { score, fit, fidelity, ratings, covered, ceiling, trialRows, trialError, liveSeries }
})(typeof window !== 'undefined' ? window : globalThis)
