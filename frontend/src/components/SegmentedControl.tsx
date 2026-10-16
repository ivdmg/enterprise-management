import type { ComponentType } from 'react';

export interface SegmentedControlOption<T extends string = string> {
  value: T;
  label: string;
  shortLabel?: string;
  icon?: ComponentType<{ className?: string }>;
  badge?: number | string;
}

export interface SegmentedControlProps<T extends string = string> {
  options: SegmentedControlOption<T>[];
  value: T;
  onChange: (value: T) => void;
  size?: 'sm' | 'md';
  className?: string;
  fullWidth?: boolean;
}

export function SegmentedControl<T extends string = string>({
  options,
  value,
  onChange,
  size = 'md',
  className = '',
  fullWidth = false,
}: SegmentedControlProps<T>) {
  const containerSizes = {
    sm: 'p-0.5 rounded-lg gap-0.5',
    md: 'p-1 rounded-xl gap-1',
  };

  const itemSizes = {
    sm: 'px-2.5 py-1 text-xs min-h-[32px] rounded-md',
    md: 'px-3.5 py-1.5 text-xs sm:text-sm min-h-[38px] rounded-lg',
  };

  const iconSizes = {
    sm: 'h-3.5 w-3.5',
    md: 'h-4 w-4',
  };

  return (
    <div
      role="tablist"
      className={`inline-flex items-center bg-slate-100 dark:bg-slate-800/80 border border-slate-200/60 dark:border-slate-700/60 transition-colors ${
        containerSizes[size]
      } ${fullWidth ? 'w-full' : ''} ${className}`}
    >
      {options.map((opt) => {
        const isSelected = opt.value === value;
        const Icon = opt.icon;

        return (
          <button
            key={opt.value}
            role="tab"
            aria-selected={isSelected}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`flex items-center justify-center font-medium transition-all select-none cursor-pointer ${
              fullWidth ? 'flex-1' : ''
            } ${itemSizes[size]} ${
              isSelected
                ? 'bg-white text-slate-900 dark:bg-slate-900 dark:text-slate-100 font-semibold shadow-xs border border-slate-200/80 dark:border-slate-700/80'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200 hover:bg-slate-200/50 dark:hover:bg-slate-700/50'
            }`}
          >
            {Icon && (
              <Icon
                className={`${iconSizes[size]} mr-1.5 shrink-0 ${
                  isSelected
                    ? 'text-slate-900 dark:text-slate-100'
                    : 'text-slate-400 dark:text-slate-500'
                }`}
              />
            )}
            <span className={opt.shortLabel ? 'hidden sm:inline' : ''}>{opt.label}</span>
            {opt.shortLabel && <span className="sm:hidden">{opt.shortLabel}</span>}

            {opt.badge !== undefined && (
              <span
                className={`ml-1.5 px-1.5 py-0.2 rounded-full text-[10px] font-semibold leading-tight ${
                  isSelected
                    ? 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200'
                    : 'bg-slate-200/70 text-slate-600 dark:bg-slate-700 dark:text-slate-400'
                }`}
              >
                {opt.badge}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
