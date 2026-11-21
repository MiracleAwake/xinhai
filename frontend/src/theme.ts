export type Theme = 'abyss' | 'mist'

const KEY = 'xinhai.theme'

/** 夜潜优先：这是参考稿里用户在夜晚看到的那套，也是「心海」最像自己的样子 */
export function loadTheme(): Theme {
  const v = localStorage.getItem(KEY)
  return v === 'mist' || v === 'abyss' ? v : 'abyss'
}

export function saveTheme(t: Theme) {
  localStorage.setItem(KEY, t)
  document.documentElement.dataset.theme = t
}

export function applyTheme(t: Theme) {
  document.documentElement.dataset.theme = t
}
