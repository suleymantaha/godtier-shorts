import type { ReactNode, MouseEventHandler } from 'react';
import { clsx } from 'clsx';

interface IconButtonBaseProps {
  label: string;
  icon: ReactNode;
  className?: string;
  variant?: 'ghost' | 'subtle' | 'primary';
}

interface IconButtonAsButton extends IconButtonBaseProps {
  onClick: MouseEventHandler<HTMLButtonElement>;
  href?: never;
  download?: never;
}

interface IconButtonAsLink extends IconButtonBaseProps {
  href: string;
  download?: boolean;
  onClick?: never;
}

export type IconButtonProps = IconButtonAsButton | IconButtonAsLink;

const variantStyles: Record<NonNullable<IconButtonProps['variant']>, string> = {
  ghost: 'bg-transparent hover:bg-foreground/10 text-muted-foreground hover:text-foreground',
  subtle: 'bg-foreground/10 hover:bg-foreground/20 text-foreground',
  primary: 'bg-primary/20 hover:bg-primary/40 text-primary',
};

export function IconButton({ label, icon, className, variant = 'ghost', ...rest }: IconButtonProps) {
  const base = clsx(
    'inline-flex items-center justify-center rounded-full min-w-[40px] min-h-[40px] p-2 transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary',
    variantStyles[variant],
    className,
  );

  if ('href' in rest && rest.href) {
    return (
      <a href={rest.href} download={rest.download} aria-label={label} className={base}>
        {icon}
      </a>
    );
  }

  return (
    <button type="button" onClick={(rest as IconButtonAsButton).onClick} aria-label={label} className={base}>
      {icon}
    </button>
  );
}
