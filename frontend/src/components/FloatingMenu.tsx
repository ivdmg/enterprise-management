import { useLayoutEffect, useRef, type HTMLAttributes, type Ref } from 'react';

export function FloatingMenu({ menuRef, className = '', ...props }: HTMLAttributes<HTMLDivElement> & {
  menuRef?: Ref<HTMLDivElement>;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const panel = ref.current;
    const anchor = panel?.previousElementSibling;
    if (!panel || !anchor) return;
    panel.showPopover();
    const position = () => {
      const rect = anchor.getBoundingClientRect();
      const width = Math.min(Math.max(rect.width, 208), window.innerWidth - 16);
      const below = window.innerHeight - rect.bottom - 14;
      const above = rect.top - 14;
      const up = below < Math.min(244, panel.scrollHeight) && above > below;
      const left = Math.max(8, Math.min(rect.left, window.innerWidth - width - 8));
      Object.assign(panel.style, {
        width: `${width}px`, left: `${left}px`, maxHeight: `${Math.min(244, Math.max(0, up ? above : below))}px`,
        top: up ? 'auto' : `${rect.bottom + 6}px`,
        bottom: up ? `${window.innerHeight - rect.top + 6}px` : 'auto',
      });
    };
    position();
    window.addEventListener('scroll', position, true);
    window.addEventListener('resize', position);
    return () => {
      window.removeEventListener('scroll', position, true);
      window.removeEventListener('resize', position);
      panel.hidePopover();
    };
  }, []);
  return <div {...props} popover="manual" className={`workspace-floating-menu ${className}`} ref={node => {
    ref.current = node;
    if (typeof menuRef === 'function') menuRef(node);
    else if (menuRef) menuRef.current = node;
  }} />;
}
