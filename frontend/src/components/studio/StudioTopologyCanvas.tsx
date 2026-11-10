import React, { useRef, useState, useEffect, useCallback } from 'react';
import {
  Plus,
  Cpu,
  Server,
  ZoomIn,
  ZoomOut,
  Maximize2,
  GitCompare,
  CheckCircle2,
  FileCode,
  ShieldCheck,
} from 'lucide-react';
import {
  ComponentCategory,
  HarnessComponent,
  HarnessSnapshot,
} from '../../types';
import { CATEGORY_META, HarnessLeverAxis, WALKTHROUGH_ORDER } from './categoryMeta';
import { useLang } from '../../i18n/LangContext';

/**
 * Lifecycle stages of an agent harness. Exported for structural reference and tests.
 */
export const STUDIO_STAGES: {
  id: string;
  zh: string;
  en: string;
  hintZh: string;
  hintEn: string;
  cats: ComponentCategory[];
}[] = [
  {
    id: 'context',
    zh: '① 上下文构建',
    en: '① Context',
    hintZh: '决定智能体「知道什么」',
    hintEn: 'What the agent knows',
    cats: ['c1', 'c2', 'c3', 'c6'],
  },
  {
    id: 'delegation',
    zh: '② 任务委托',
    en: '② Delegation',
    hintZh: '决定「谁来做」',
    hintEn: 'Who does the work',
    cats: ['c5'],
  },
  {
    id: 'interface',
    zh: '③ 工具接口',
    en: '③ Interface',
    hintZh: '决定「能做什么」',
    hintEn: 'What it can do',
    cats: ['c4', 'c7', 'c9'],
  },
  {
    id: 'middleware',
    zh: '④ 运行中间件',
    en: '④ Middleware',
    hintZh: '决定「如何被约束与观测」',
    hintEn: 'How it is observed & bounded',
    cats: ['c8'],
  },
];

interface StudioTopologyCanvasProps {
  components: HarnessComponent[];
  selectedCategory: ComponentCategory | null;
  /** Categories with at least one component matching the active search/source filter. */
  matchedCategories: Set<ComponentCategory>;
  filterActive: boolean;
  /** Category -> component id currently injected into the targeted run (session-local). */
  appliedByCategory: Partial<Record<ComponentCategory, string>>;
  /** Live snapshot of the selected Run/Task/Stage harness from backend. */
  sandboxSnapshot?: HarnessSnapshot | null;
  /** Active lever highlight filter ('ALL' | 'INV' | 'DOM' | 'PRIOR_SEAM'). */
  leverFilter?: 'ALL' | 'INV' | 'DOM' | 'PRIOR_SEAM';
  onChangeLeverFilter?: (lever: 'ALL' | 'INV' | 'DOM' | 'PRIOR_SEAM') => void;
  /** Active walkthrough step index (0..8) or null when idle. */
  activeWalkthroughStep?: number | null;
  targetSummary?: string;
  onSelectCategory: (cat: ComponentCategory) => void;
  onCreateInCategory: (cat: ComponentCategory) => void;
}

interface NodePosition {
  cat: ComponentCategory;
  x: number;
  y: number;
  width: number;
  zone: 'left' | 'center' | 'right';
  portY: number;
}

const CANVAS_WIDTH = 1520;
const CANVAS_HEIGHT = 670;

const NODE_POSITIONS: NodePosition[] = [
  // Left Zone: ① Context Construction (x: 55, width: 370)
  { cat: 'c1', x: 55, y: 125, width: 370, zone: 'left', portY: 178 },
  { cat: 'c2', x: 55, y: 252, width: 370, zone: 'left', portY: 305 },
  { cat: 'c3', x: 55, y: 379, width: 370, zone: 'left', portY: 432 },
  { cat: 'c6', x: 55, y: 506, width: 370, zone: 'left', portY: 559 },

  // Center Zone: ④ Middleware Hook (x: 560, width: 400)
  { cat: 'c8', x: 560, y: 310, width: 400, zone: 'center', portY: 365 },

  // Right Zone: ② Delegation & ③ Tool Interface / Protocol (x: 1095, width: 370)
  { cat: 'c5', x: 1095, y: 125, width: 370, zone: 'right', portY: 178 },
  { cat: 'c4', x: 1095, y: 252, width: 370, zone: 'right', portY: 305 },
  { cat: 'c7', x: 1095, y: 379, width: 370, zone: 'right', portY: 432 },
  { cat: 'c9', x: 1095, y: 506, width: 370, zone: 'right', portY: 559 },
];

const LEVER_BADGE_STYLE: Record<HarnessLeverAxis, string> = {
  INV: 'bg-blue-500/15 text-blue-700 dark:text-blue-300 border-blue-500/30',
  DOM: 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30',
  PRIOR: 'bg-purple-500/15 text-purple-700 dark:text-purple-300 border-purple-500/30',
  SEAM: 'bg-teal-500/15 text-teal-700 dark:text-teal-300 border-teal-500/30',
};

export const StudioTopologyCanvas: React.FC<StudioTopologyCanvasProps> = ({
  components,
  selectedCategory,
  matchedCategories,
  filterActive,
  appliedByCategory,
  sandboxSnapshot,
  leverFilter = 'ALL',
  onChangeLeverFilter,
  activeWalkthroughStep = null,
  targetSummary,
  onSelectCategory,
  onCreateInCategory,
}) => {
  const { lang, tx } = useLang();
  const isZh = lang === 'zh';
  const containerRef = useRef<HTMLDivElement>(null);

  // Dynamic Theme state tracker
  const [isDark, setIsDark] = useState<boolean>(() => {
    return typeof document !== 'undefined' && document.documentElement.classList.contains('dark');
  });

  useEffect(() => {
    const checkTheme = () => {
      setIsDark(document.documentElement.classList.contains('dark'));
    };
    checkTheme();
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.attributeName === 'class') {
          checkTheme();
        }
      });
    });
    observer.observe(document.documentElement, { attributes: true });
    return () => observer.disconnect();
  }, []);

  // Pan & Zoom state
  const [zoom, setZoom] = useState(0.92);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0, panX: 0, panY: 0 });

  const handleFit = useCallback(() => {
    if (!containerRef.current) return;
    const containerWidth = containerRef.current.clientWidth;
    const containerHeight = containerRef.current.clientHeight || 620;
    const scaleX = containerWidth / CANVAS_WIDTH;
    const scaleY = containerHeight / CANVAS_HEIGHT;
    const scale = Math.min(Math.max(Math.min(scaleX, scaleY) * 0.98, 0.45), 1.12);
    setZoom(scale);
    const initialPanX = Math.max((containerWidth - CANVAS_WIDTH * scale) / 2, 0);
    const initialPanY = Math.max((containerHeight - CANVAS_HEIGHT * scale) / 2, 0);
    setPan({ x: initialPanX, y: initialPanY });
  }, []);

  useEffect(() => {
    handleFit();
    window.addEventListener('resize', handleFit);
    return () => window.removeEventListener('resize', handleFit);
  }, [handleFit]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (e.button !== 0) return;
    if ((e.target as HTMLElement).closest('button')) return;
    setIsDragging(true);
    dragStartRef.current = {
      x: e.clientX,
      y: e.clientY,
      panX: pan.x,
      panY: pan.y,
    };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    const dx = e.clientX - dragStartRef.current.x;
    const dy = e.clientY - dragStartRef.current.y;
    setPan({
      x: dragStartRef.current.panX + dx,
      y: dragStartRef.current.panY + dy,
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  const isCategoryLeverMatched = (cat: ComponentCategory): boolean => {
    if (leverFilter === 'ALL') return true;
    const lv = CATEGORY_META[cat].lever;
    if (leverFilter === 'INV') return lv === 'INV';
    if (leverFilter === 'DOM') return lv === 'DOM';
    return lv === 'PRIOR' || lv === 'SEAM';
  };

  const activeWalkthroughCat: ComponentCategory | null =
    activeWalkthroughStep !== null && activeWalkthroughStep >= 0 && activeWalkthroughStep < WALKTHROUGH_ORDER.length
      ? WALKTHROUGH_ORDER[activeWalkthroughStep]
      : null;

  const formatChars = (chars: number): string => {
    if (chars >= 1000) return `${(chars / 1000).toFixed(1)}k`;
    return `${chars}`;
  };

  return (
    <div className="relative w-full rounded-2xl bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-800/90 shadow-xl dark:shadow-2xl overflow-hidden select-none bg-tech-grid transition-colors duration-300">
      {/* Ambient Vignette Overlay */}
      <div
        className={`absolute inset-0 pointer-events-none transition-opacity duration-300 ${
          isDark
            ? 'bg-[radial-gradient(ellipse_100%_100%_at_50%_50%,rgba(15,23,42,0.35),rgba(2,6,23,0.92))]'
            : 'bg-[radial-gradient(ellipse_100%_100%_at_50%_50%,rgba(241,245,249,0.25),rgba(248,250,252,0.85))]'
        }`}
      />

      {/* 1. INTEGRATED CANVAS TITLEBAR (Matches MetroPipelineCanvas) */}
      <div className="relative z-20 flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 border-b border-slate-200 dark:border-slate-800 bg-white/95 dark:bg-slate-900/90 backdrop-blur-md">
        {/* Left: Viewport Controls */}
        <div className="flex items-center gap-2.5">
          <div className="flex items-center gap-1.5 pr-2.5 border-r border-slate-200 dark:border-slate-800 text-xs font-bold text-slate-800 dark:text-slate-200">
            <span className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
            <span>{tx('c1 ~ c9 环绕式运行时拓扑大屏', 'c1 ~ c9 Runtime Surface Topology')}</span>
          </div>

          <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800/80 p-1 rounded-xl border border-slate-200 dark:border-slate-700/80">
            <button
              type="button"
              onClick={() => setZoom((prev) => Math.min(prev + 0.1, 1.4))}
              className="p-1 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-white dark:hover:bg-slate-700 rounded-lg transition-colors cursor-pointer"
              title={tx('放大画布', 'Zoom In')}
            >
              <ZoomIn className="w-3.5 h-3.5" />
            </button>
            <span className="font-mono text-xs text-slate-700 dark:text-slate-300 px-1 min-w-[2.8rem] text-center font-semibold">
              {Math.round(zoom * 100)}%
            </span>
            <button
              type="button"
              onClick={() => setZoom((prev) => Math.max(prev - 0.1, 0.45))}
              className="p-1 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-white dark:hover:bg-slate-700 rounded-lg transition-colors cursor-pointer"
              title={tx('缩小画布', 'Zoom Out')}
            >
              <ZoomOut className="w-3.5 h-3.5" />
            </button>
            <div className="w-px h-3.5 bg-slate-200 dark:bg-slate-700 mx-0.5" />
            <button
              type="button"
              onClick={handleFit}
              className="flex items-center gap-1 px-2 py-0.5 text-xs font-semibold text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-white dark:hover:bg-slate-700 rounded-lg transition-colors cursor-pointer"
              title={tx('自适应居中', 'Fit to Screen')}
            >
              <Maximize2 className="w-3 h-3" />
              <span>{tx('自适应', 'Fit')}</span>
            </button>
          </div>
        </div>

        {/* Right: Interactive Dual-Lever Track Filter & Legend */}
        <div className="flex items-center gap-2 flex-wrap text-xs">
          <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-950/90 p-1 rounded-xl border border-slate-200 dark:border-slate-800">
            <button
              type="button"
              onClick={() => onChangeLeverFilter?.('ALL')}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-all cursor-pointer ${
                leverFilter === 'ALL'
                  ? 'bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-xs'
                  : 'text-slate-500 hover:text-slate-800 dark:hover:text-slate-200'
              }`}
            >
              {tx('全部经络 (c1~c9)', 'All Tracks')}
            </button>
            <button
              type="button"
              onClick={() => onChangeLeverFilter?.(leverFilter === 'INV' ? 'ALL' : 'INV')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-all cursor-pointer ${
                leverFilter === 'INV'
                  ? 'bg-blue-600 text-white shadow-xs'
                  : 'text-slate-600 dark:text-slate-300 hover:text-blue-600 dark:hover:text-blue-400'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-blue-400 shadow-[0_0_6px_#3b82f6]" />
              <span>{tx('INV 不变性轨 (c1, c2, c4)', 'INV Track (c1, c2, c4)')}</span>
            </button>
            <button
              type="button"
              onClick={() => onChangeLeverFilter?.(leverFilter === 'DOM' ? 'ALL' : 'DOM')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-all cursor-pointer ${
                leverFilter === 'DOM'
                  ? 'bg-amber-500 text-white shadow-xs'
                  : 'text-slate-600 dark:text-slate-300 hover:text-amber-600 dark:hover:text-amber-400'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-amber-400 shadow-[0_0_6px_#f59e0b]" />
              <span>{tx('DOM 领域轨 (c5~c8)', 'DOM Track (c5~c8)')}</span>
            </button>
            <button
              type="button"
              onClick={() => onChangeLeverFilter?.(leverFilter === 'PRIOR_SEAM' ? 'ALL' : 'PRIOR_SEAM')}
              className={`flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-[11px] font-semibold transition-all cursor-pointer ${
                leverFilter === 'PRIOR_SEAM'
                  ? 'bg-purple-600 text-white shadow-xs'
                  : 'text-slate-600 dark:text-slate-300 hover:text-purple-600 dark:hover:text-purple-400'
              }`}
            >
              <span className="w-2 h-2 rounded-full bg-purple-400 shadow-[0_0_6px_#a855f7]" />
              <span>{tx('先验与接缝 (c3, c9)', 'Prior & Seam (c3, c9)')}</span>
            </button>
          </div>
        </div>
      </div>

      {/* 2. INTERACTIVE SVG TOPOLOGY CANVAS */}
      <div
        ref={containerRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        className={`w-full h-[615px] cursor-${
          isDragging ? 'grabbing' : 'grab'
        } overflow-hidden relative`}
      >
        <div
          style={{
            width: CANVAS_WIDTH,
            height: CANVAS_HEIGHT,
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: '0 0',
            transition: isDragging ? 'none' : 'transform 0.35s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
          className="relative"
        >
          {/* SVG TRACKS & CONDUITS LAYER */}
          <svg
            width={CANVAS_WIDTH}
            height={CANVAS_HEIGHT}
            className="absolute inset-0 pointer-events-none"
          >
            <defs>
              <filter id="studioGlow" x="-30%" y="-30%" width="160%" height="160%">
                <feGaussianBlur stdDeviation="4" result="blur1" />
                <feGaussianBlur stdDeviation="8" result="blur2" />
                <feMerge>
                  <feMergeNode in="blur2" />
                  <feMergeNode in="blur1" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>

              <linearGradient id="studioLoopGrad" x1="1" y1="0" x2="0" y2="0">
                <stop offset="0%" stopColor={isDark ? '#2dd4bf' : '#0d9488'} />
                <stop offset="50%" stopColor={isDark ? '#c084fc' : '#9333ea'} />
                <stop offset="100%" stopColor={isDark ? '#38bdf8' : '#0284c7'} />
              </linearGradient>
            </defs>

            {/* ZONE BACKDROP REGIONS */}
            {/* Zone 1: Left Context Construction */}
            <rect
              x="35"
              y="72"
              width="410"
              height="565"
              rx="24"
              fill="#0ea5e9"
              fillOpacity={isDark ? '0.04' : '0.05'}
              stroke="#0ea5e9"
              strokeOpacity={isDark ? '0.25' : '0.35'}
              strokeDasharray="4 4"
            />
            {/* Zone 2: Center Core, Middleware & Sandbox */}
            <rect
              x="535"
              y="72"
              width="450"
              height="565"
              rx="24"
              fill="#6366f1"
              fillOpacity={isDark ? '0.04' : '0.05'}
              stroke="#6366f1"
              strokeOpacity={isDark ? '0.28' : '0.35'}
              strokeDasharray="4 4"
            />
            {/* Zone 3: Right Delegation & Tool Interface */}
            <rect
              x="1075"
              y="72"
              width="410"
              height="565"
              rx="24"
              fill="#10b981"
              fillOpacity={isDark ? '0.04' : '0.05'}
              stroke="#10b981"
              strokeOpacity={isDark ? '0.25' : '0.35'}
              strokeDasharray="4 4"
            />

            {/* OVERHEAD S5 REFLECTION LOOP ARC (Sandbox ➔ Context Prior c3/c6) */}
            <path
              d="M 760 475 C 760 460, 1020 560, 1020 350 C 1020 80, 960 40, 760 40 L 280 40 C 210 40, 210 75, 210 120"
              fill="none"
              stroke="url(#studioLoopGrad)"
              strokeWidth="3"
              strokeOpacity={isDark ? '0.55' : '0.45'}
              strokeDasharray="8 10"
              className="animate-flow-dash-reverse"
            />
            <g transform="translate(760, 40)">
              <rect
                x="-185"
                y="-16"
                width="370"
                height="32"
                rx="16"
                fill={isDark ? '#0f172a' : '#ffffff'}
                stroke={isDark ? '#c084fc' : '#9333ea'}
                strokeWidth="1.5"
              />
              <circle cx="-162" cy="0" r="4" fill={isDark ? '#e879f9' : '#9333ea'} className="animate-ping" />
              <circle cx="-162" cy="0" r="3.5" fill={isDark ? '#c084fc' : '#9333ea'} />
              <text
                x="-144"
                y="4"
                fill={isDark ? '#f8fafc' : '#1e1b4b'}
                fontSize="11"
                fontWeight="700"
                fontFamily="sans-serif"
              >
                {isZh
                  ? '⟲ S5 反思经验沉淀闭环 (沙箱轨迹 ➔ 演进 c3 记忆 / c6 技能 / c1 提示词)'
                  : '⟲ S5 Reflection Loop (Sandbox Trajectory ➔ Evolves c3 / c6 / c1)'}
              </text>
            </g>

            {/* LEFT CONDUITS: c1, c2, c3, c6 ➔ Frozen LLM Core (x: 425 ➔ x: 560, y: 195) */}
            {NODE_POSITIONS.filter((n) => n.zone === 'left').map((pos) => {
              const meta = CATEGORY_META[pos.cat];
              const isLeverActive = isCategoryLeverMatched(pos.cat);
              const isWalkActive = activeWalkthroughCat === pos.cat;
              const isSelected = selectedCategory === pos.cat;
              const strokeHex =
                meta.lever === 'INV'
                  ? isDark
                    ? '#60a5fa'
                    : '#2563eb'
                  : meta.lever === 'DOM'
                    ? isDark
                      ? '#fbbf24'
                      : '#d97706'
                    : isDark
                      ? '#c084fc'
                      : '#9333ea';
              const pathD = `M 425 ${pos.portY} C 490 ${pos.portY}, 500 200, 560 200`;

              return (
                <g key={`conduit-left-${pos.cat}`} opacity={isLeverActive ? 1 : 0.2}>
                  <path
                    d={pathD}
                    fill="none"
                    stroke={isDark ? 'rgba(255,255,255,0.06)' : '#e2e8f0'}
                    strokeWidth="9"
                    strokeLinecap="round"
                  />
                  <path
                    d={pathD}
                    fill="none"
                    stroke={strokeHex}
                    strokeWidth={isWalkActive || isSelected ? '4.5' : '3'}
                    strokeLinecap="round"
                    filter={isWalkActive || isSelected ? 'url(#studioGlow)' : undefined}
                  />
                  <path
                    d={pathD}
                    fill="none"
                    stroke={isDark ? '#ffffff' : strokeHex}
                    strokeWidth="2.5"
                    strokeDasharray="6 12"
                    className="animate-flow-dash"
                  />
                </g>
              );
            })}

            {/* CENTER VERTICAL SPINE: Frozen LLM Core (y=265) ⇄ c8 Hooks (y=310..420) ➔ Sandbox (y=470) */}
            <g>
              <line
                x1="760"
                y1="260"
                x2="760"
                y2="475"
                stroke={isDark ? 'rgba(255,255,255,0.08)' : '#cbd5e1'}
                strokeWidth="12"
                strokeLinecap="round"
              />
              <line
                x1="760"
                y1="260"
                x2="760"
                y2="475"
                stroke={isDark ? '#fb7185' : '#e11d48'}
                strokeWidth="4"
                strokeLinecap="round"
                filter="url(#studioGlow)"
              />
              <line
                x1="760"
                y1="260"
                x2="760"
                y2="475"
                stroke="#ffffff"
                strokeWidth="3"
                strokeDasharray="6 10"
                className="animate-flow-dash"
              />
            </g>

            {/* RIGHT CONDUITS: Center Core/Hook Bus (x: 960, y: 365) ➔ c5, c4, c7, c9 (x: 1095) */}
            {NODE_POSITIONS.filter((n) => n.zone === 'right').map((pos) => {
              const meta = CATEGORY_META[pos.cat];
              const isLeverActive = isCategoryLeverMatched(pos.cat);
              const isWalkActive = activeWalkthroughCat === pos.cat;
              const isSelected = selectedCategory === pos.cat;
              const strokeHex =
                meta.lever === 'INV'
                  ? isDark
                    ? '#34d399'
                    : '#059669'
                  : meta.lever === 'DOM'
                    ? isDark
                      ? '#fbbf24'
                      : '#d97706'
                    : isDark
                      ? '#2dd4bf'
                      : '#0d9488';
              const pathD = `M 960 365 C 1025 365, 1030 ${pos.portY}, 1095 ${pos.portY}`;
              const toSandboxD = `M 1095 ${pos.portY + 24} C 1040 ${pos.portY + 24}, 1020 545, 960 545`;

              return (
                <g key={`conduit-right-${pos.cat}`} opacity={isLeverActive ? 1 : 0.2}>
                  {/* Outbound from Core/Hook to Tool/Subagent */}
                  <path
                    d={pathD}
                    fill="none"
                    stroke={isDark ? 'rgba(255,255,255,0.06)' : '#e2e8f0'}
                    strokeWidth="9"
                    strokeLinecap="round"
                  />
                  <path
                    d={pathD}
                    fill="none"
                    stroke={strokeHex}
                    strokeWidth={isWalkActive || isSelected ? '4.5' : '3'}
                    strokeLinecap="round"
                    filter={isWalkActive || isSelected ? 'url(#studioGlow)' : undefined}
                  />
                  <path
                    d={pathD}
                    fill="none"
                    stroke={isDark ? '#ffffff' : strokeHex}
                    strokeWidth="2.5"
                    strokeDasharray="6 12"
                    className="animate-flow-dash"
                  />
                  {/* Execution materialized into Substrate Sandbox */}
                  <path
                    d={toSandboxD}
                    fill="none"
                    stroke={strokeHex}
                    strokeWidth="1.75"
                    strokeOpacity={isDark ? '0.45' : '0.35'}
                    strokeDasharray="4 6"
                  />
                </g>
              );
            })}
          </svg>

          {/* ZONE HEADER BANNERS */}
          <div
            style={{ left: 55, top: 82, width: 370 }}
            className="absolute z-10 flex items-center justify-between px-3 py-1 rounded-xl bg-white/90 dark:bg-slate-900/90 border border-sky-500/30 shadow-xs"
          >
            <span className="text-xs font-extrabold text-slate-900 dark:text-white">
              {tx('① 上下文构建 (Context Construction)', '① Context Construction')}
            </span>
            <span className="text-[10px] font-mono text-sky-600 dark:text-sky-400 font-semibold">
              {tx('决定「知道什么」 · c1/c2/c3/c6', 'c1 · c2 · c3 · c6')}
            </span>
          </div>

          <div
            style={{ left: 560, top: 82, width: 400 }}
            className="absolute z-10 flex items-center justify-between px-3 py-1 rounded-xl bg-white/90 dark:bg-slate-900/90 border border-indigo-500/30 shadow-xs"
          >
            <span className="text-xs font-extrabold text-slate-900 dark:text-white">
              {tx('④ 冻结核心 · 拦截钩子 · 隔离沙箱', '④ Core LLM · Middleware · Sandbox')}
            </span>
            <span className="text-[10px] font-mono text-indigo-600 dark:text-indigo-400 font-semibold">
              θ_LLM ⇄ c8 ➔ Sandbox
            </span>
          </div>

          <div
            style={{ left: 1095, top: 82, width: 370 }}
            className="absolute z-10 flex items-center justify-between px-3 py-1 rounded-xl bg-white/90 dark:bg-slate-900/90 border border-emerald-500/30 shadow-xs"
          >
            <span className="text-xs font-extrabold text-slate-900 dark:text-white">
              {tx('② 委派 & ③ 工具协议 (Delegation & Tools)', '② Delegation & ③ Tools')}
            </span>
            <span className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 font-semibold">
              {tx('决定「谁做与能做什么」 · c5/c4/c7/c9', 'c5 · c4 · c7 · c9')}
            </span>
          </div>

          {/* CENTER ANCHOR 1: FROZEN LLM CORE (x: 560, y: 125, w: 400) */}
          <div
            style={{ left: 560, top: 125, width: 400 }}
            className={`absolute z-20 rounded-2xl p-3.5 border backdrop-blur-xl transition-all ${
              activeWalkthroughCat === 'c8'
                ? 'bg-indigo-950/95 text-white border-cyan-400 ring-2 ring-cyan-400/40 shadow-xl scale-102'
                : 'bg-gradient-to-br from-slate-900 via-indigo-950/95 to-slate-900 text-white border-indigo-500/40 shadow-lg'
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-xl bg-cyan-500/20 border border-cyan-400/30 text-cyan-300">
                  <Cpu className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-extrabold tracking-tight text-white">
                      {tx('冻结核心大模型 (Frozen LLM Core)', 'Frozen LLM Core')}
                    </span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30 font-bold">
                      θ_LLM ≡ Const
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-300 mt-0.5">
                    {tx(
                      '零梯度参数更新 · 所有能力演进 100% 由外周 c1~c9 组件树承载',
                      'Zero weight updates · Intelligence emerges purely via c1..c9 harness'
                    )}
                  </p>
                </div>
              </div>
            </div>
            <div className="mt-2.5 pt-2 border-t border-white/10 flex items-center justify-between text-[10px] font-mono text-cyan-200/90">
              <span>Prompt = c1 ⊕ c2 ⊕ c3 ⊕ c6</span>
              <span className="text-emerald-300 flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>{tx('公平评测基石', 'Fair Benchmark Anchor')}</span>
              </span>
            </div>
          </div>

          {/* CENTER ANCHOR 2: SUBSTRATE EXECUTION SANDBOX (x: 560, y: 475, w: 400) */}
          <div
            style={{ left: 560, top: 475, width: 400 }}
            className={`absolute z-20 rounded-2xl p-3.5 border backdrop-blur-xl transition-all ${
              activeWalkthroughCat === 'c9'
                ? 'bg-teal-950/95 text-white border-teal-400 ring-2 ring-teal-400/40 shadow-xl scale-102'
                : 'bg-gradient-to-br from-slate-900 via-teal-950/90 to-slate-900 text-white border-teal-500/40 shadow-lg'
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="p-2 rounded-xl bg-teal-500/20 border border-teal-400/30 text-teal-300 shrink-0">
                  <Server className="w-5 h-5" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-extrabold tracking-tight text-white truncate">
                      {tx('Substrate 隔离执行沙箱', 'Substrate Execution Sandbox')}
                    </span>
                    <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-teal-500/20 text-teal-300 border border-teal-500/30 font-bold shrink-0">
                      OpenCode / Pi
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-300 mt-0.5 truncate">
                    {targetSummary
                      ? tx(`当前挂载目标: ${targetSummary}`, `Mounted Target: ${targetSummary}`)
                      : tx(
                          '物化 (Materialize) c1~c9 全套文件并执行真实工具调用循环',
                          'Materializes c1..c9 harness files and executes isolated tool rollouts'
                        )}
                  </p>
                </div>
              </div>
            </div>
            <div className="mt-2.5 pt-2 border-t border-white/10 flex items-center justify-between text-[10px] font-mono text-teal-200/90">
              <span>harnesses/{sandboxSnapshot?.label || 'agg1'}/</span>
              <span className="text-amber-300">
                {sandboxSnapshot?.raw_files
                  ? tx(
                      `已物化 ${Object.keys(sandboxSnapshot.raw_files).length} 个沙箱文件`,
                      `${Object.keys(sandboxSnapshot.raw_files).length} files materialized`
                    )
                  : tx('等待沙箱同步', 'Ready to materialize')}
              </span>
            </div>
          </div>

          {/* 9 HARNESS SURFACE COMPONENT NODES (c1..c9) */}
          {NODE_POSITIONS.map((pos) => {
            const { cat } = pos;
            const meta = CATEGORY_META[cat];
            const Icon = meta.icon;
            const items = components.filter((c) => c.category === cat);
            const customCount = items.filter((c) => c.source === 'custom').length;
            const isSelected = selectedCategory === cat;
            const isWalkActive = activeWalkthroughCat === cat;
            const isLeverMatched = isCategoryLeverMatched(cat);
            const dimmed =
              (filterActive && !matchedCategories.has(cat)) || (!isLeverMatched && !isSelected);
            const hit = filterActive && matchedCategories.has(cat);
            const applied = appliedByCategory[cat];
            const sandboxCat = sandboxSnapshot?.by_category?.[cat];

            return (
              <div
                key={cat}
                style={{
                  left: pos.x,
                  top: pos.y,
                  width: pos.width,
                  boxShadow: isWalkActive
                    ? `0 0 28px ${meta.glowHex}`
                    : isSelected
                      ? `0 0 22px ${meta.glowHex}`
                      : undefined,
                }}
                className={`group absolute z-20 rounded-2xl border backdrop-blur-xl transition-all duration-200 ${
                  isWalkActive
                    ? 'bg-white dark:bg-slate-900 border-blue-500 ring-2 ring-blue-500/50 scale-104 z-30'
                    : isSelected
                      ? 'bg-white dark:bg-slate-900 border-blue-500 ring-2 ring-blue-500/40 shadow-lg scale-102 z-30'
                      : hit
                        ? 'bg-white/95 dark:bg-slate-900/95 border-amber-400 ring-2 ring-amber-400/30 shadow-md'
                        : 'bg-white/92 dark:bg-slate-900/90 border-slate-200/90 dark:border-slate-800 hover:border-blue-500/60 hover:-translate-y-0.5 shadow-sm hover:shadow-md'
                } ${dimmed ? 'opacity-30' : ''}`}
              >
                {/* Walkthrough Active Floating Pill */}
                {isWalkActive && (
                  <div className="absolute -top-2.5 right-3 px-2 py-0.5 rounded-full text-[9px] font-bold bg-blue-600 text-white shadow-md flex items-center gap-1 animate-bounce">
                    <span className="w-1.5 h-1.5 rounded-full bg-white animate-ping" />
                    <span>
                      {tx(`信号流步骤 ${meta.walkthroughStep + 1}/9`, `Step ${meta.walkthroughStep + 1}/9`)}
                    </span>
                  </div>
                )}

                <button
                  type="button"
                  onClick={() => onSelectCategory(cat)}
                  className="w-full text-left p-3 cursor-pointer"
                >
                  {/* Row 1: Category Code + Title + Lever Axis Badge + Library Count */}
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <div className={`p-1.5 rounded-xl border ${meta.border} ${meta.bgLight} shrink-0`}>
                        <Icon className={`w-4 h-4 ${meta.color}`} />
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-xs font-mono font-black uppercase text-blue-600 dark:text-cyan-400">
                            {cat}
                          </span>
                          <span className="text-xs font-bold text-slate-900 dark:text-white truncate">
                            {isZh ? meta.cnName : meta.name}
                          </span>
                        </div>
                        <div className="text-[10px] font-mono text-slate-400 truncate">
                          {sandboxCat?.exists ? sandboxCat.primary_path : meta.defaultPath}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <span
                        className={`text-[9px] font-mono font-bold px-1.5 py-0.5 rounded border ${
                          LEVER_BADGE_STYLE[meta.lever]
                        }`}
                      >
                        {isZh ? meta.leverBadgeZh : meta.leverBadgeEn}
                      </span>
                      <span
                        className="text-[10px] px-1.5 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 font-mono font-bold"
                        title={tx(`组件库中共有 ${items.length} 个实例`, `${items.length} instances in library`)}
                      >
                        {items.length}
                      </span>
                    </div>
                  </div>

                  {/* Row 2: Live Sandbox Telemetry & Custom Status Pills */}
                  <div className="mt-2 pt-1.5 border-t border-slate-100 dark:border-slate-800/80 flex flex-wrap items-center justify-between gap-1.5 text-[10px]">
                    <div className="flex flex-wrap items-center gap-1">
                      {/* Live Sandbox File Status */}
                      {sandboxCat?.exists ? (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-sky-500/10 text-sky-700 dark:text-sky-300 border border-sky-500/20 font-mono font-semibold">
                          <FileCode className="w-3 h-3 text-sky-500" />
                          <span>
                            {tx(
                              `沙箱生效 · ${formatChars(sandboxCat.char_count)}字`,
                              `Live · ${formatChars(sandboxCat.char_count)}c`
                            )}
                          </span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-800/70 text-slate-400 font-mono">
                          <span>{tx('沙箱未挂载', 'Unmounted in sandbox')}</span>
                        </span>
                      )}

                      {/* Evolved vs Base Badge */}
                      {sandboxCat?.diff_from_base && (
                        <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-700 dark:text-amber-300 border border-amber-500/30 font-mono font-bold">
                          <GitCompare className="w-2.5 h-2.5 text-amber-500" />
                          <span>{tx('Δ 演进变更', 'Δ Evolved')}</span>
                        </span>
                      )}

                      {/* Custom count badge */}
                      {customCount > 0 && (
                        <span className="px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-600 dark:text-purple-300 border border-purple-500/20 font-semibold">
                          {tx(`${customCount} 自定义`, `${customCount} custom`)}
                        </span>
                      )}

                      {/* Session injected badge */}
                      {applied && (
                        <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border border-emerald-500/30 font-semibold">
                          <CheckCircle2 className="w-2.5 h-2.5" />
                          <span>{tx('已注入', 'Injected')}</span>
                        </span>
                      )}
                    </div>

                    <span className="text-[10px] text-blue-600 dark:text-cyan-400 font-semibold group-hover:translate-x-0.5 transition-transform pr-5">
                      {tx('检视/装配 ➔', 'Inspect ➔')}
                    </span>
                  </div>
                </button>

                {/* Quick Create Button */}
                <button
                  type="button"
                  title={tx(`在 ${cat} 新建组件`, `New ${cat} component`)}
                  onClick={(e) => {
                    e.stopPropagation();
                    onCreateInCategory(cat);
                  }}
                  className="absolute bottom-2 right-2 p-1 rounded-lg text-slate-400 hover:text-blue-600 dark:hover:text-cyan-400 hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
