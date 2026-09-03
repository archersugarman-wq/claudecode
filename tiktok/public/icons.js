'use strict';
/** Small inline-SVG icon set (stroke-based, 24x24 viewbox). No icon font/deps. */
const ICONS = {
  home: '<path d="M4 11.5 12 4l8 7.5"/><path d="M6 10v9a1 1 0 0 0 1 1h4v-6h2v6h4a1 1 0 0 0 1-1v-9"/>',
  compass: '<circle cx="12" cy="12" r="9"/><path d="M15.5 8.5 13 13l-4.5 2.5L11 11l4.5-2.5Z"/>',
  plus: '<rect x="3" y="3" width="18" height="18" rx="5"/><path d="M12 8v8M8 12h8"/>',
  inbox: '<path d="M4 12h4l1.5 3h5L16 12h4"/><path d="M4 12 6 5h12l2 7v6a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z"/>',
  user: '<circle cx="12" cy="8" r="3.6"/><path d="M4.5 20c1.4-4 4.2-6 7.5-6s6.1 2 7.5 6"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  heart: '<path d="M12 20.5s-7.6-4.7-10-9.4C.4 7.8 2.3 4.5 5.7 4c2.2-.3 4.2.9 6.3 3 2.1-2.1 4.1-3.3 6.3-3 3.4.5 5.3 3.8 3.7 7.1-2.4 4.7-10 9.4-10 9.4Z"/>',
  heartFilled: '<path fill="currentColor" stroke="none" d="M12 20.5s-7.6-4.7-10-9.4C.4 7.8 2.3 4.5 5.7 4c2.2-.3 4.2.9 6.3 3 2.1-2.1 4.1-3.3 6.3-3 3.4.5 5.3 3.8 3.7 7.1-2.4 4.7-10 9.4-10 9.4Z"/>',
  comment: '<path d="M4 12c0-4.4 3.8-8 8.5-8s8.5 3.6 8.5 8-3.8 8-8.5 8c-1.2 0-2.4-.2-3.4-.7L4 21l1.4-4.4C4.5 15.3 4 13.7 4 12Z"/>',
  share: '<path d="M13 5 20 12 13 19"/><path d="M20 12H10c-3.3 0-6 2.7-6 6v1"/>',
  music: '<path d="M9 18V5l11-2v13"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>',
  play: '<path fill="currentColor" stroke="none" d="M7 4.5v15l13-7.5Z"/>',
  pause: '<rect x="6" y="4" width="4" height="16" rx="1"/><rect x="14" y="4" width="4" height="16" rx="1"/>',
  volumeUp: '<path d="M4 9v6h4l5 4V5L8 9Z"/><path d="M17 8.5a5 5 0 0 1 0 7"/><path d="M19.5 6a9 9 0 0 1 0 12"/>',
  volumeMute: '<path d="M4 9v6h4l5 4V5L8 9Z"/><path d="m19 9-5 6M14 9l5 6"/>',
  x: '<path d="m5 5 14 14M19 5 5 19"/>',
  back: '<path d="m15 5-7 7 7 7"/>',
  check: '<path d="m5 12 5 5L20 7"/>',
  checkBadge: '<circle fill="currentColor" stroke="none" cx="12" cy="12" r="10"/><path stroke="#fff" fill="none" d="m7.5 12.5 3 3 6-6.5"/>',
  more: '<circle cx="5" cy="12" r="1.6" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none"/><circle cx="19" cy="12" r="1.6" fill="currentColor" stroke="none"/>',
  trash: '<path d="M4 7h16M9 7V5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2M6 7l1 13a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1l1-13"/>',
  camera: '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M8 7 9.5 4h5L16 7"/><circle cx="12" cy="13.5" r="3.5"/>',
  cameraFlip: '<path d="M4 8h3l1.5-2h7L17 8h3v10H4Z"/><path d="M9 13a3 3 0 1 1 6 0 3 3 0 0 1-6 0Z"/><path d="M9.5 4.5 8 6M14.5 4.5 16 6"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none"/>',
  upload: '<path d="M12 16V4M8 8l4-4 4 4"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
  edit: '<path d="M4 20h4l10-10-4-4L4 16Z"/><path d="m14 6 4 4"/>',
  logout: '<path d="M9 4H6a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h3"/><path d="M14 8l4 4-4 4M18 12H9"/>',
  send: '<path d="m4 12 16-8-6 16-3-6-7-2Z"/>',
  spinner: '<path d="M12 3a9 9 0 1 0 9 9"/>',
  bell: '<path d="M6 10a6 6 0 0 1 12 0c0 4 1.5 5.5 2 6H4c.5-.5 2-2 2-6Z"/><path d="M10 19a2 2 0 0 0 4 0"/>',
  users: '<circle cx="9" cy="9" r="3.2"/><path d="M3.5 19c1-3 3-4.5 5.5-4.5s4.5 1.5 5.5 4.5"/><circle cx="17" cy="8.2" r="2.6"/><path d="M15.5 14.6c2.4.3 4 1.7 4.9 4.4"/>',
};

function icon(name, size = 24, cls = '') {
  const paths = ICONS[name] || '';
  return `<svg class="icon ${cls}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
}

window.icon = icon;
