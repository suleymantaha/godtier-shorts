import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, Check } from 'lucide-react';
import { clsx } from 'clsx';

export interface SelectOption {
    value: string;
    label: string | React.ReactNode;
}

interface SelectProps {
    id?: string;
    options: SelectOption[];
    value: string;
    onChange: (value: string) => void;
    label?: string;
    icon?: React.ReactNode;
    placeholder?: string;
    className?: string;
    disabled?: boolean;
}

export const Select: React.FC<SelectProps> = ({
    id,
    options,
    value,
    onChange,
    label,
    icon,
    placeholder = 'Seçiniz...',
    className,
    disabled = false,
}) => {
    const [isOpen, setIsOpen] = useState(false);
    const containerRef = useRef<HTMLDivElement>(null);
    
    const selectedOption = options.find(opt => opt.value === value);

    // Close on click outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
                setIsOpen(false);
            }
        };
        document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, []);

    // Accessibility: Close on Escape
    useEffect(() => {
        const handleKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') setIsOpen(false);
        };
        if (isOpen) {
            window.addEventListener('keydown', handleKeyDown);
        }
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [isOpen]);

    return (
        <div className={clsx("relative", label && "space-y-2", className)} ref={containerRef}>
            {label && (
                <label
                    htmlFor={id}
                    className="text-[11px] font-medium text-muted-foreground uppercase tracking-widest ml-1"
                >
                    {label}
                </label>
            )}
            
            <div className="relative">
                <button
                    id={id}
                    type="button"
                    onClick={() => !disabled && setIsOpen(!isOpen)}
                    disabled={disabled}
                    className={clsx(
                        "input-field w-full flex items-center justify-between text-left transition-all duration-300",
                        isOpen ? "border-primary/50 ring-1 ring-primary/20" : "hover:border-primary/30",
                        disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer"
                    )}
                    aria-haspopup="listbox"
                    aria-expanded={isOpen}
                >
                    <div className="flex items-center gap-3 overflow-hidden">
                        {icon && <span className="shrink-0 text-muted-foreground">{icon}</span>}
                        <span className="truncate text-sm">
                            {selectedOption ? selectedOption.label : <span className="text-muted-foreground italic">{placeholder}</span>}
                        </span>
                    </div>
                    <ChevronDown 
                        className={clsx(
                            "w-4 h-4 text-muted-foreground transition-transform duration-300 shrink-0",
                            isOpen && "rotate-180 text-primary"
                        )} 
                    />
                </button>

                <AnimatePresence>
                    {isOpen && (
                        <motion.div
                            initial={{ opacity: 0, y: -10, scale: 0.95 }}
                            animate={{ opacity: 1, y: 4, scale: 1 }}
                            exit={{ opacity: 0, y: -10, scale: 0.95 }}
                            transition={{ duration: 0.2, ease: "easeOut" }}
                            className="absolute z-[100] w-full min-w-[200px] glass-card !bg-background/95 border-primary/20 shadow-2xl overflow-hidden py-1.5 backdrop-blur-3xl"
                            role="listbox"
                        >
                            <div className="max-h-[240px] overflow-y-auto custom-scrollbar">
                                {options.map((option) => (
                                    <button
                                        key={option.value}
                                        type="button"
                                        onClick={() => {
                                            onChange(option.value);
                                            setIsOpen(false);
                                        }}
                                        className={clsx(
                                            "w-full flex items-center justify-between px-4 py-2.5 text-sm transition-colors relative group",
                                            option.value === value 
                                                ? "bg-primary/10 text-primary" 
                                                : "text-foreground/80 hover:bg-foreground/5 hover:text-foreground"
                                        )}
                                        role="option"
                                        aria-selected={option.value === value}
                                    >
                                        <span className="truncate">{option.label}</span>
                                        {option.value === value && (
                                            <motion.div
                                                initial={{ scale: 0 }}
                                                animate={{ scale: 1 }}
                                                className="shrink-0"
                                            >
                                                <Check className="w-4 h-4 text-primary" />
                                            </motion.div>
                                        )}
                                        
                                        {/* Hover Indicator */}
                                        <div className="absolute left-0 top-0 bottom-0 w-1 bg-primary scale-y-0 group-hover:scale-y-100 transition-transform origin-center" />
                                    </button>
                                ))}
                            </div>
                        </motion.div>
                    )}
                </AnimatePresence>
            </div>
        </div>
    );
};
