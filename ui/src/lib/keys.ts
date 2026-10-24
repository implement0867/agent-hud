/** The modifier key of the platform, as the page names it: ⌘ on Apple platforms, Ctrl elsewhere. */
export const mod = /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl";
