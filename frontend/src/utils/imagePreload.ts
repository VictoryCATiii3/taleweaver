/**
 * Warms the browser image cache, e.g. for thumbnails of a tab that is not open yet.
 * Each URL is requested once per page load; the Image objects are kept until loaded so the
 * requests are not garbage-collected mid-flight.
 */
const requested = new Set<string>()
const inFlight = new Set<HTMLImageElement>()

export function preloadImages(urls: Iterable<string | null | undefined>): void {
  for (const url of urls) {
    if (!url || requested.has(url)) {
      continue
    }
    requested.add(url)
    const img = new Image()
    img.decoding = 'async'
    const done = () => inFlight.delete(img)
    img.onload = done
    img.onerror = () => {
      done()
      // Allow a retry later (e.g. thumbnail generated on demand after a 404).
      requested.delete(url)
    }
    inFlight.add(img)
    img.src = url
  }
}
