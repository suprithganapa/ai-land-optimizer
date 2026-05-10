import { create } from 'zustand'

const useStore = create((set) => ({
  drawnPolygon:    null,
  setDrawnPolygon: (polygon) => set({ drawnPolygon: polygon }),

  zoningResult:    null,
  setZoningResult: (result) => set({ zoningResult: result }),

  layout:    null,
  setLayout: (layout) => set({ layout }),

  financials:    null,
  setFinancials: (financials) => set({ financials }),

  isLoading:         false,
  setIsLoading:      (val) => set({ isLoading: val }),

  loadingMessage:    '',
  setLoadingMessage: (msg) => set({ loadingMessage: msg }),

  selectedParetoIndex:    0,
  setSelectedParetoIndex: (i) => set({ selectedParetoIndex: i }),

  reset: () => set({
    drawnPolygon:         null,
    zoningResult:         null,
    layout:               null,
    financials:           null,
    isLoading:            false,
    loadingMessage:       '',
    selectedParetoIndex:  0,
  }),
}))

export default useStore