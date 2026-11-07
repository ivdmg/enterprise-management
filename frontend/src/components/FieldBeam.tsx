import { useState, type ComponentProps, type ReactNode } from 'react';
import { BorderBeam } from 'border-beam';
import { useTheme } from '@/context/ThemeContext';

function FieldBeam({ children }: { children: ReactNode }) {
  const [focused, setFocused] = useState(false);
  const { isDark } = useTheme();
  return <BorderBeam className="workspace-field-beam" size="md" colorVariant="mono" staticColors strength={0.56}
    theme={isDark ? 'dark' : 'light'} active={focused}
    onFocusCapture={() => setFocused(true)} onBlurCapture={() => setFocused(false)}>
    {children}
  </BorderBeam>;
}

export function BeamInput(props: ComponentProps<'input'>) {
  return <FieldBeam><input {...props} /></FieldBeam>;
}

export function BeamTextarea(props: ComponentProps<'textarea'>) {
  return <FieldBeam><textarea {...props} /></FieldBeam>;
}
