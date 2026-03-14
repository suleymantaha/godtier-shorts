import type { ChangeEvent, FC } from 'react';

interface RangeSliderProps {
    min: number;
    max: number;
    step?: number;
    start: number;
    end: number;
    startLabel?: string;
    endLabel?: string;
    onChange: (start: number, end: number) => void;
}

export const RangeSlider: FC<RangeSliderProps> = ({
    min,
    max,
    step = 0.1,
    start,
    end,
    startLabel = 'Start time',
    endLabel = 'End time',
    onChange,
}) => {
    const minPos = ((start - min) / (max - min)) * 100;
    const maxPos = ((end - min) / (max - min)) * 100;

    const handleStartChange = (e: ChangeEvent<HTMLInputElement>) => {
        const value = Math.min(Number(e.target.value), end - 0.5);
        onChange(value, end);
    };

    const handleEndChange = (e: ChangeEvent<HTMLInputElement>) => {
        const value = Math.max(Number(e.target.value), start + 0.5);
        onChange(start, value);
    };

    return (
        <div className="relative w-full h-12 flex items-center group" role="group" aria-label="Time range selector">
            <div className="absolute w-full h-3 bg-white/10 rounded-full overflow-hidden">
                <div
                    className="absolute h-full bg-primary/40"
                    style={{ left: `${minPos}%`, right: `${100 - maxPos}%` }}
                />
            </div>

            <label className="sr-only" htmlFor="range-start">{startLabel}</label>
            <input
                id="range-start"
                type="range"
                min={min}
                max={max}
                step={step}
                value={start}
                onChange={handleStartChange}
                aria-valuemin={min}
                aria-valuemax={max}
                aria-valuenow={start}
                className="absolute w-full pointer-events-none appearance-none bg-transparent [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-7 [&::-webkit-slider-thumb]:h-7 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-primary [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:shadow-[0_0_10px_rgba(0,242,255,0.45)] z-10"
            />

            <label className="sr-only" htmlFor="range-end">{endLabel}</label>
            <input
                id="range-end"
                type="range"
                min={min}
                max={max}
                step={step}
                value={end}
                onChange={handleEndChange}
                aria-valuemin={min}
                aria-valuemax={max}
                aria-valuenow={end}
                className="absolute w-full pointer-events-none appearance-none bg-transparent [&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-7 [&::-webkit-slider-thumb]:h-7 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-accent [&::-webkit-slider-thumb]:border-2 [&::-webkit-slider-thumb]:border-white [&::-webkit-slider-thumb]:cursor-pointer [&::-webkit-slider-thumb]:shadow-[0_0_10px_rgba(255,0,127,0.45)] z-10"
            />
        </div>
    );
};
