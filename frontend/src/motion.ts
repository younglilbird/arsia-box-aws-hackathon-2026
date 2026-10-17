import { useEffect, useLayoutEffect, useRef, type RefObject } from 'react';

type Surface = 'step' | 'panel' | 'source';
const active = new Map<Element, Animation>();
const easeOut = 'cubic-bezier(0.23, 1, 0.32, 1)';
const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const keyboardInput = () => document.documentElement.dataset.inputModality === 'keyboard';

export function cancelSurface(element: Element | null) {
  if (!element) return;
  active.get(element)?.cancel();
  active.delete(element);
}

export function animateSurface(element: HTMLElement | null, surface: Surface) {
  if (!element) return;
  if (keyboardInput()) { cancelSurface(element); return; }
  const previous = active.get(element);
  const current = previous?.playState === 'running' ? getComputedStyle(element) : undefined;
  const reduce = reducedMotion();
  const distance = surface === 'step' ? 10 : surface === 'panel' ? 5 : 3;
  const initialTransform = reduce ? 'none' : `translateY(${distance}px) scale(${surface === 'step' ? '.985' : '1'})`;
  const from = { opacity: current?.opacity || (reduce ? '.86' : surface === 'source' ? '.65' : '0'), transform: reduce ? 'none' : current?.transform || initialTransform };
  cancelSurface(element);
  const duration = reduce ? 80 : surface === 'step' ? 220 : 160;
  const animation = element.animate([from, { opacity: '1', transform: 'none' }], { duration, easing: easeOut });
  active.set(element, animation);
  animation.finished.then(() => { if (active.get(element) === animation) active.delete(element); }).catch(() => {});
}

export function useInputModality() {
  useEffect(() => {
    const pointer = () => { document.documentElement.dataset.inputModality = 'pointer'; };
    const keyboard = () => {
      document.documentElement.dataset.inputModality = 'keyboard';
      active.forEach(animation => animation.cancel()); active.clear();
    };
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const preferenceChanged = () => { active.forEach(animation => animation.cancel()); active.clear(); };
    document.addEventListener('pointerdown', pointer, true);
    document.addEventListener('keydown', keyboard, true);
    media.addEventListener('change', preferenceChanged);
    return () => {
      document.removeEventListener('pointerdown', pointer, true);
      document.removeEventListener('keydown', keyboard, true);
      media.removeEventListener('change', preferenceChanged);
      active.forEach(animation => animation.cancel()); active.clear();
    };
  }, []);
}

export function useSurfaceMotion(target: RefObject<HTMLDivElement | null>, key: string, surface: Surface) {
  const previous = useRef(key);
  useLayoutEffect(() => {
    if (previous.current === key) return;
    previous.current = key;
    if (surface === 'panel' && target.current) target.current.scrollTop = 0;
    animateSurface(target.current, surface);
  }, [target, key, surface]);
  useEffect(() => () => cancelSurface(target.current), [target]);
}

export function scrollMotion(): ScrollBehavior { return reducedMotion() || keyboardInput() ? 'instant' : 'smooth'; }

export function revealSource(container: HTMLElement | null, target: HTMLElement) {
  if (container && container.scrollHeight > container.clientHeight) {
    const top = container.scrollTop + target.getBoundingClientRect().top - container.getBoundingClientRect().top - 14;
    const behavior = Math.abs(top - container.scrollTop) > container.clientHeight ? 'instant' : scrollMotion();
    container.scrollTo({ top: Math.max(0, top), behavior });
  } else {
    target.scrollIntoView({ behavior: scrollMotion(), block: 'nearest' });
  }
  target.focus({ preventScroll: true });
  animateSurface(target, 'source');
}
