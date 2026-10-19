import { useState, useRef, useEffect, useId, type KeyboardEvent } from 'react';
import { ChevronDown, Check } from 'lucide-react';

export interface SelectOption {
  value: string;
  label: string;
  icon?: React.ComponentType<{ className?: string }>;
}

export interface SelectProps {
  options: SelectOption[];
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  id?: string;
  disabled?: boolean;
  size?: 'sm' | 'md';
}

export function Select({
  options,
  value,
  onChange,
  placeholder = 'Выберите...',
  className = '',
  id,
  disabled = false,
  size = 'md',
}: SelectProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [focusedIndex, setFocusedIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const generatedId = useId();
  const selectId = id || generatedId;

  const selectedIndex = options.findIndex((o) => o.value === value);
  const selected = options[selectedIndex];

  // Close on click outside
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    if (isOpen) {
      document.addEventListener('mousedown', handleClick);
    }
    return () => document.removeEventListener('mousedown', handleClick);
  }, [isOpen]);

  const openSelect = () => {
    setIsOpen(true);
    setFocusedIndex(selectedIndex >= 0 ? selectedIndex : 0);
  };

  const toggleSelect = () => {
    if (isOpen) {
      setIsOpen(false);
    } else {
      openSelect();
    }
  };

  // Keyboard navigation
  const handleKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return;

    if (!isOpen) {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openSelect();
      }
      return;
    }

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        setFocusedIndex((prev) => (prev < options.length - 1 ? prev + 1 : 0));
        break;
      case 'ArrowUp':
        e.preventDefault();
        setFocusedIndex((prev) => (prev > 0 ? prev - 1 : options.length - 1));
        break;
      case 'Enter':
      case ' ':
        e.preventDefault();
        if (focusedIndex >= 0 && focusedIndex < options.length) {
          onChange(options[focusedIndex].value);
          setIsOpen(false);
        }
        break;
      case 'Escape':
        e.preventDefault();
        setIsOpen(false);
        break;
      case 'Tab':
        setIsOpen(false);
        break;
    }
  };

  const sizeClasses = {
    sm: 'px-2.5 py-1.5 text-xs min-h-[34px] rounded-lg',
    md: 'px-3 py-2 text-xs sm:text-sm min-h-[38px] rounded-lg',
  };

  return (
    <div ref={containerRef} className={`relative inline-block ${className}`} id={selectId}>
      {/* Trigger Button */}
      <button
        type="button"
        disabled={disabled}
        onClick={toggleSelect}
        onKeyDown={handleKeyDown}
        aria-haspopup="listbox"
        aria-expanded={isOpen}
        className={`w-full flex items-center justify-between gap-2 border border-[var(--card-border)] bg-[var(--card-bg)] text-[var(--text-main)] hover:bg-[var(--card-subtle)] hover:border-[var(--card-subtle-border)] transition-colors focus:outline-none focus:ring-1 focus:ring-[var(--card-border)] shadow-2xs disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer ${
          sizeClasses[size]
        }`}
      >
        <span className="flex items-center gap-2 truncate">
          {selected?.icon && <selected.icon className="h-3.5 w-3.5 shrink-0 text-[var(--text-sub)]" />}
          <span className={selected ? 'font-medium truncate' : 'text-[var(--text-muted)] truncate'}>
            {selected ? selected.label : placeholder}
          </span>
        </span>
        <ChevronDown
          className={`h-4 w-4 text-[var(--text-muted)] shrink-0 transition-transform duration-200 ${
            isOpen ? 'rotate-180' : ''
          }`}
        />
      </button>

      {/* Popover Menu */}
      {isOpen && (
        <div
          ref={listRef}
          role="listbox"
          tabIndex={-1}
          className="absolute z-[100] mt-1.5 w-full min-w-[160px] bg-[var(--card-bg)] border border-[var(--card-border)] rounded-xl shadow-xl p-1 max-h-60 overflow-y-auto scrollbar-none animate-in fade-in zoom-in-95 duration-100 text-[var(--text-main)]"
        >
          {options.map((option, idx) => {
            const isSelected = option.value === value;
            const isFocused = idx === focusedIndex;
            const Icon = option.icon;

            return (
              <button
                key={option.value}
                role="option"
                aria-selected={isSelected}
                type="button"
                onClick={() => {
                  onChange(option.value);
                  setIsOpen(false);
                }}
                onMouseEnter={() => setFocusedIndex(idx)}
                className={`w-full flex items-center justify-between px-2.5 py-1.5 text-xs sm:text-sm rounded-lg transition-colors cursor-pointer text-left select-none ${
                  isSelected
                    ? 'bg-[var(--card-subtle)] text-[var(--text-main)] font-semibold border border-[var(--card-border)]'
                    : isFocused
                    ? 'bg-[var(--card-subtle)]/70 text-[var(--text-main)]'
                    : 'text-[var(--text-sub)] hover:text-[var(--text-main)]'
                }`}
              >
                <div className="flex items-center gap-2 truncate">
                  {Icon && <Icon className="h-3.5 w-3.5 shrink-0 text-[var(--text-muted)]" />}
                  <span className="truncate">{option.label}</span>
                </div>
                {isSelected && (
                  <Check className="h-3.5 w-3.5 text-[var(--text-main)] shrink-0 ml-2" />
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
