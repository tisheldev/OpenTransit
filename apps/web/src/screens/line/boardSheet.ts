import { useEffect } from "react";
import { useSheet } from "../../shell/sheet";

/**
 * The half sheet opens as tall as the board draws it (Stop 548, Line 596, Ride 628 of
 * 844 px): a little over half, so the actions and the first rows are in view.
 */
export function useBoardSheet(share: number): void {
  const { fitHalf } = useSheet();
  useEffect(() => {
    if (typeof window === "undefined") return;
    fitHalf(Math.round(window.innerHeight * share));
    return () => fitHalf(null);
  }, [fitHalf, share]);
}
