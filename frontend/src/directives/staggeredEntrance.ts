import type { ObjectDirective } from 'vue'

const panels = [
  '.page-view > :not(div)', '.page-view > .page-heading', '.interview-heading',
  '.hero-card', '.practice-section > .section-heading', '.practice-card', '.card',
  '.profile-form > .form-card-title', '.profile-form .form-section', '.profile-form > .form-actions',
  '.conversation-header', '.conversation-intro', '.conversation-message', '.ready-panel',
  '.clarification-options', '.answer-composer', '.report-actions',
  '.auth-story > .brand', '.auth-story-copy', '.auth-story-footer', '.auth-panel', '.auth-copyright',
].join(',')
const groups = '.profile-form, .conversation-card'
const cleanup = new WeakMap<HTMLElement, () => void>()

export const staggeredEntrance: ObjectDirective<HTMLElement> = {
  mounted(root) {
    const reduced = matchMedia('(prefers-reduced-motion: reduce)')
    const seen = new WeakSet<Element>()
    const observed = new Set<Element>()
    const entering = new Set<Element>()
    const animations = new Map<Element, Animation>()
    let frame = 0

    function play() {
      frame = 0
      const positions = [...entering].filter(element => root.contains(element) && element.getClientRects().length)
        .map(element => ({ element, rect: element.getBoundingClientRect() }))
        .sort((a, b) => a.rect.top - b.rect.top || a.rect.left - b.rect.left)
      entering.clear()
      // Cards in the same visual row enter left to right despite small alignment differences.
      let order = 0
      while (positions.length) {
        const rowTop = positions[0].rect.top
        const row = positions.filter(item => item.rect.top - rowTop <= 8).sort((a, b) => a.rect.left - b.rect.left)
        positions.splice(0, row.length)
        for (const { element } of row) {
          if (reduced.matches || element.contains(document.activeElement) || element.matches(':target')) continue
          const animation = element.animate(
            [{ opacity: 0, translate: '0 9px' }, { opacity: 1, translate: '0 0' }],
            { duration: 280, delay: order++ * 300, easing: 'cubic-bezier(.2, .7, .2, 1)', fill: 'backwards' },
          )
          animations.set(element, animation)
          animation.onfinish = animation.oncancel = () => animations.delete(element)
        }
      }
    }

    const intersections = new IntersectionObserver(entries => {
      for (const { target, isIntersecting } of entries) {
        if (!isIntersecting || !root.contains(target)) continue
        seen.add(target)
        observed.delete(target)
        intersections.unobserve(target)
        entering.add(target)
      }
      if (!frame && entering.size) frame = requestAnimationFrame(play)
    })

    function scan() {
      for (const element of observed) {
        if (!root.contains(element)) { intersections.unobserve(element); observed.delete(element) }
      }
      for (const element of root.querySelectorAll(panels)) {
        if (element.matches(groups) || seen.has(element) || observed.has(element)) continue
        observed.add(element)
        intersections.observe(element)
      }
    }
    const mutations = new MutationObserver(scan)
    function revealFocus(event: FocusEvent) {
      for (const [element, animation] of animations) {
        if (event.target instanceof Node && element.contains(event.target)) animation.cancel()
      }
    }
    function changePreference() {
      if (reduced.matches) for (const animation of animations.values()) animation.cancel()
    }
    mutations.observe(root, { childList: true, subtree: true })
    root.addEventListener('focusin', revealFocus)
    reduced.addEventListener('change', changePreference)
    scan()
    cleanup.set(root, () => {
      mutations.disconnect()
      intersections.disconnect()
      cancelAnimationFrame(frame)
      for (const animation of animations.values()) animation.cancel()
      root.removeEventListener('focusin', revealFocus)
      reduced.removeEventListener('change', changePreference)
    })
  },
  unmounted(root) {
    cleanup.get(root)?.()
    cleanup.delete(root)
  },
}
