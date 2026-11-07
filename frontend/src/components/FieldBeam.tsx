import { useEffect, useRef, useState, type ComponentProps, type ReactNode } from 'react';
import { BorderBeam } from 'border-beam';
import { useTheme } from '@/context/ThemeContext';

export function FieldBeam({ children, className = '' }: { children: ReactNode; className?: string }) {
  const { isDark } = useTheme();
  const glow = useRef<HTMLSpanElement>(null);
  const [field, setField] = useState<HTMLInputElement | HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const halo = glow.current;
    if (!field || !halo) return;
    const mirror = document.createElement('div');
    const marker = document.createElement('span');
    Object.assign(mirror.style, { position: 'fixed', visibility: 'hidden', left: '-10000px', top: '0' });
    document.body.append(mirror);
    const update = () => {
      const index = field.selectionEnd;
      const parent = halo.offsetParent;
      delete halo.dataset.visible;
      if (index === null || !parent || field.selectionStart !== index) return;

      const style = getComputedStyle(field);
      const rect = field.getBoundingClientRect();
      const origin = parent.getBoundingClientRect();
      const multiline = field instanceof HTMLTextAreaElement;
      const paddingLeft = parseFloat(style.paddingLeft);
      const lineHeight = parseFloat(style.lineHeight) || parseFloat(style.fontSize) * 1.2;
      Object.assign(mirror.style, {
        font: style.font, lineHeight: `${lineHeight}px`, letterSpacing: style.letterSpacing,
        whiteSpace: multiline ? 'pre-wrap' : 'pre', overflowWrap: 'break-word',
        width: multiline ? `${field.clientWidth - paddingLeft - parseFloat(style.paddingRight)}px` : 'max-content',
      });
      const value = field instanceof HTMLInputElement && field.type === 'password' ? '•'.repeat(field.value.length) : field.value;
      marker.textContent = value.slice(index) || '\u200b';
      mirror.replaceChildren(document.createTextNode(value.slice(0, index)), marker);
      const cursor = marker.getClientRects()[0];
      if (!cursor) return;
      const bounds = mirror.getBoundingClientRect();
      const x = rect.left + field.clientLeft + paddingLeft + cursor.left - bounds.left - field.scrollLeft;
      const y = multiline
        ? rect.top + field.clientTop + parseFloat(style.paddingTop) + cursor.top - bounds.top - field.scrollTop + cursor.height / 2
        : rect.top + rect.height / 2;
      if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) return;
      Object.assign(halo.style, { left: `${x - origin.left}px`, top: `${y - origin.top}px`, height: `${lineHeight * .85}px` });
      halo.dataset.visible = 'true';
    };
    let frame = 0;
    const schedule = () => { cancelAnimationFrame(frame); frame = requestAnimationFrame(update); };
    const events = ['input', 'keyup', 'click', 'scroll', 'select'] as const;
    events.forEach(event => field.addEventListener(event, schedule));
    document.addEventListener('selectionchange', schedule);
    const observer = new ResizeObserver(schedule);
    observer.observe(field);
    schedule();
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      events.forEach(event => field.removeEventListener(event, schedule));
      document.removeEventListener('selectionchange', schedule);
      mirror.remove();
    };
  }, [field]);
  return <BorderBeam className={`workspace-field-beam ${className}`} size="md" colorVariant="mono"
    staticColors strength={1} brightness={1.65} theme={isDark ? 'dark' : 'light'}
    onFocusCapture={event => {
      const target = event.target;
      if (target instanceof HTMLTextAreaElement || (target instanceof HTMLInputElement && target.selectionEnd !== null)) setField(target);
    }}
    onBlurCapture={() => setField(null)}>
    {children}
    {field && <span ref={glow} className="workspace-caret-glow" aria-hidden="true" />}
  </BorderBeam>;
}

export function BeamInput(props: ComponentProps<'input'>) {
  return <FieldBeam><input {...props} /></FieldBeam>;
}

export function BeamTextarea(props: ComponentProps<'textarea'>) {
  return <FieldBeam><textarea {...props} /></FieldBeam>;
}
