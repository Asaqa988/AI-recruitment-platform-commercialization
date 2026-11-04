const paths = {
  search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></>,
  phone: <path d="M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z" />,
  shield: <><path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6l-8-3Z" /><path d="m9 12 2 2 4-4" /></>,
  pen: <><path d="M4 20h4L19 9l-4-4L4 16v4Z" /><path d="m13.5 6.5 4 4" /></>,
  arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
  check: <path d="m5 12 5 5L20 7" />,
  download: <><path d="M12 4v11m-5-5 5 5 5-5" /><path d="M5 20h14" /></>,
  menu: <path d="M4 7h16M4 12h16M4 17h16" />,
  close: <path d="m6 6 12 12M18 6 6 18" />,
  plus: <path d="M12 5v14M5 12h14" />,
  file: <><path d="M6 3h8l4 4v14H6V3Z" /><path d="M14 3v4h4M9 12h6M9 16h6" /></>,
  chat: <><path d="M4 5h16v11H9l-5 4V5Z" /><path d="M8 10h8" /></>,
  scale: <><path d="M12 4v16M6 20h12M5 8h14" /><path d="m5 8-3 6h6L5 8Zm14 0-3 6h6l-3-6Z" /></>,
  mail: <><path d="M3 6h18v12H3V6Z" /><path d="m3 7 9 7 9-7" /></>,
  coin: <><circle cx="12" cy="12" r="8" /><path d="M12 8v8m-2-6h3a1.5 1.5 0 0 1 0 3h-2a1.5 1.5 0 0 0 0 3h3" /></>,
  list: <path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01" />,
  lock: <><path d="M6 11h12v9H6v-9Z" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>,
  trash: <><path d="M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13" /></>,
  edit: <><path d="M4 20h4L19 9l-4-4L4 16v4Z" /></>,
}

export default function Icon({ name, size = 22 }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2"
      strokeLinecap="square" strokeLinejoin="miter" aria-hidden="true" className="icon">
      {paths[name]}
    </svg>
  )
}
