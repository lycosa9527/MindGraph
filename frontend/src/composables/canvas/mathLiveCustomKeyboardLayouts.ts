/**
 * Custom MathLive virtual keyboard layouts for MindGraph (K-12 math + mhchem chemistry).
 * Used with window.mathVirtualKeyboard.layouts — each layout appears as a tab in the switcher.
 *
 * K-12 and chemistry use multiple MathLive *layers* (pages) with `switchKeyboardLayer` so each
 * screen stays short; `displayEditToolbar: false` avoids an extra toolbar row on custom layouts.
 */
import type { VirtualKeyboardKeycap, VirtualKeyboardLayout, VirtualKeyboardName } from 'mathlive'

/**
 * Built-ins before MindGraph tabs. MathLive expands `'default'` into numeric, symbols,
 * alphabetic, and greek — do not list those names again or tabs duplicate.
 */
export const MATHLIVE_BASE_LAYOUTS_BEFORE_CUSTOM: readonly VirtualKeyboardName[] = ['default']

const K12_LAYER = {
  p1: 'mindgraph-k12-p1',
  p2: 'mindgraph-k12-p2',
  p3: 'mindgraph-k12-p3',
  p4: 'mindgraph-k12-p4',
} as const

const CHEM_LAYER = {
  p1: 'mindgraph-chem-p1',
  p2: 'mindgraph-chem-p2',
} as const

const K12_EQ_LAYER = {
  p1: 'mindgraph-k12-eq-p1',
  p2: 'mindgraph-k12-eq-p2',
  p3: 'mindgraph-k12-eq-p3',
  p4: 'mindgraph-k12-eq-p4',
} as const

const K12_CHEMF_LAYER = {
  p1: 'mindgraph-k12-chemf-p1',
  p2: 'mindgraph-k12-chemf-p2',
  p3: 'mindgraph-k12-chemf-p3',
} as const

type PartialKeycap = string | Partial<VirtualKeyboardKeycap>

function switchLayerKey(
  pageNum: number,
  layerId: string,
  tooltip: string
): Partial<VirtualKeyboardKeycap> {
  return {
    class: 'action',
    label: String(pageNum),
    tooltip,
    command: ['switchKeyboardLayer', layerId],
  }
}

function k12NavRow(tooltips: { p1: string; p2: string; p3: string; p4: string }): PartialKeycap[] {
  return [
    switchLayerKey(1, K12_LAYER.p1, tooltips.p1),
    switchLayerKey(2, K12_LAYER.p2, tooltips.p2),
    switchLayerKey(3, K12_LAYER.p3, tooltips.p3),
    switchLayerKey(4, K12_LAYER.p4, tooltips.p4),
  ]
}

function chemNavRow(tooltips: { p1: string; p2: string }): PartialKeycap[] {
  return [switchLayerKey(1, CHEM_LAYER.p1, tooltips.p1), switchLayerKey(2, CHEM_LAYER.p2, tooltips.p2)]
}

function k12EqNavRow(tooltips: { p1: string; p2: string; p3: string; p4: string }): PartialKeycap[] {
  return [
    switchLayerKey(1, K12_EQ_LAYER.p1, tooltips.p1),
    switchLayerKey(2, K12_EQ_LAYER.p2, tooltips.p2),
    switchLayerKey(3, K12_EQ_LAYER.p3, tooltips.p3),
    switchLayerKey(4, K12_EQ_LAYER.p4, tooltips.p4),
  ]
}

function k12ChemFormNavRow(tooltips: { p1: string; p2: string; p3: string }): PartialKeycap[] {
  return [
    switchLayerKey(1, K12_CHEMF_LAYER.p1, tooltips.p1),
    switchLayerKey(2, K12_CHEMF_LAYER.p2, tooltips.p2),
    switchLayerKey(3, K12_CHEMF_LAYER.p3, tooltips.p3),
  ]
}

/** Short label + full LaTeX for common equation templates (same idea as `chemCe`). */
function mathInsert(label: string, latex: string, options?: { width?: VirtualKeyboardKeycap['width'] }): Partial<VirtualKeyboardKeycap> {
  return {
    label,
    latex,
    tooltip: latex,
    class: 'small',
    ...(options?.width != null ? { width: options.width } : {}),
  }
}

/** Short visible label + full `\\ce{...}` insert so keycaps stay readable for long formulas. */
function chemCe(label: string, inner: string, options?: { width?: VirtualKeyboardKeycap['width'] }): Partial<VirtualKeyboardKeycap> {
  const full = `\\ce{${inner}}`
  return {
    label,
    latex: full,
    tooltip: full,
    class: 'small',
    ...(options?.width != null ? { width: options.width } : {}),
  }
}

export type K12KeyboardPageTooltips = {
  p1: string
  p2: string
  p3: string
  p4: string
}

export type ChemistryKeyboardPageTooltips = {
  p1: string
  p2: string
}

export type K12EquationsPageTooltips = {
  p1: string
  p2: string
  p3: string
  p4: string
}

export type K12ChemFormulasPageTooltips = {
  p1: string
  p2: string
  p3: string
}

/** Localized short labels for the K-12 equations tab (LaTeX inserts stay unchanged). */
export type K12EquationsKeyLabels = {
  p1: {
    pythagorean: string
    squareSum: string
    squareDiff: string
    quadratic: string
    diffSquares: string
    slope: string
    distance: string
    pointSlope: string
    midpoint: string
    ymxb: string
    yQuad: string
    absX: string
  }
  p2: {
    circleArea: string
    circleCircum: string
    triHalfBh: string
    rectArea: string
    trapezoid: string
    circleSector: string
    prismVol: string
    pyramidVol: string
    coneVol: string
    sphereVol: string
    cylVol: string
    sphereSA: string
    spaceDiag3d: string
    rectPrismSA: string
  }
  p3: {
    sin2Cos2: string
    tanDef: string
    lawCos: string
    lawSin: string
    cosSumDiff: string
    sinSumDiff: string
    euler: string
    doubleAngle: string
  }
  p4: {
    sum1toN: string
    arithAn: string
    geomAn: string
    geomSum: string
    binomial: string
    meanXbar: string
    variance: string
    chooseNK: string
    permNK: string
  }
}

/** Localized short labels for the K-12 chem formulas tab (`\\ce{...}` inserts unchanged). */
export type K12ChemFormulasKeyLabels = {
  p1: {
    glucose: string
    ethanol: string
    acetic: string
    carbonic: string
    calciumHydroxide: string
    kmno4: string
    k2cr2o7: string
    agno3: string
    bacl2: string
    pbNitrate: string
    al2o3: string
    fe2o3: string
    sio2: string
    p4: string
    s8: string
    nh4no3: string
    na2co3: string
    kno3: string
    mgso4: string
  }
  p2: {
    photosynth: string
    respiration: string
    rusting: string
    limewater: string
    naWater: string
    mgO2: string
    nh3Synth: string
    waterElectrolysis: string
  }
  p3: {
    hno3: string
    h3po4: string
    ch3oh: string
    c2h4: string
    c2h2: string
    benzene: string
    glucose: string
    urea: string
    ammoniumNitrate: string
    bleach: string
    vinegar: string
    chalk: string
    gypsum: string
  }
}

export function buildK12MathVirtualKeyboardLayout(
  tabLabel: string,
  pageTooltips: K12KeyboardPageTooltips
): VirtualKeyboardLayout {
  const nav = k12NavRow(pageTooltips)

  return {
    id: 'mindgraph-k12',
    label: tabLabel,
    tooltip: tabLabel,
    displayEditToolbar: false,
    layers: [
      {
        id: K12_LAYER.p1,
        rows: [
          ['+', '-', '\\times', '\\div', '=', '\\neq', '\\approx'],
          ['<', '>', '\\leq', '\\geq', '\\pm', '\\cdot'],
          ['(', ')', '[', ']', '\\{', '\\}', '\\%', '^\\circ'],
          ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'],
          ['x', 'y', 'n', 'a', 'b', 'c', 'd', 'e', 'z'],
          nav,
        ],
      },
      {
        id: K12_LAYER.p2,
        rows: [
          ['x^2', 'x^3', 'x^n', 'x^{2}', 'x^{-1}', 'x^{\\frac{1}{2}}'],
          ['\\sqrt{x}', '\\sqrt[3]{x}', '\\sqrt[n]{x}', '|x|', '\\left|x\\right|'],
          ['\\frac{a}{b}', '\\dfrac{a}{b}', '\\frac{1}{2}', '\\frac{1}{4}', '\\frac{1}{3}', '\\tfrac{a}{b}'],
          ['(', ')', '[', ']', '\\{', '\\}'],
          ['\\pi', '\\infty', '\\equiv', '\\ldots', '\\cdots'],
          nav,
        ],
      },
      {
        id: K12_LAYER.p3,
        rows: [
          ['\\sin', '\\cos', '\\tan', '\\cot', '\\sec', '\\csc'],
          ['\\arcsin', '\\arccos', '\\arctan'],
          ['\\sinh', '\\cosh', '\\tanh'],
          ['\\log', '\\ln', '\\lg', '\\exp', 'e^{x}', '10^{x}'],
          ['\\deg', '\\angle', '\\triangle', '\\perp', '\\parallel'],
          nav,
        ],
      },
      {
        id: K12_LAYER.p4,
        rows: [
          ['\\alpha', '\\beta', '\\gamma', '\\delta', '\\theta', '\\lambda'],
          ['\\mu', '\\omega', '\\phi', '\\psi', '\\rho', '\\sigma'],
          ['\\Delta', '\\Sigma', '\\Pi', '\\Omega', '\\varepsilon', '\\varphi'],
          ['\\sum', '\\prod', '\\int', '\\oint', '\\iint'],
          ['\\lim', '\\lim_{x \\to \\infty}', '\\int_{a}^{b}', '\\frac{d}{dx}', '\\partial'],
          nav,
        ],
      },
    ],
  }
}

/** Curated K-12 “famous” equations (algebra, geometry, trig, sequences & stats). */
export function buildK12EquationsVirtualKeyboardLayout(
  tabLabel: string,
  pageTooltips: K12EquationsPageTooltips,
  keyLabels: K12EquationsKeyLabels
): VirtualKeyboardLayout {
  const nav = k12EqNavRow(pageTooltips)
  const L = keyLabels

  return {
    id: 'mindgraph-k12-eq',
    label: tabLabel,
    tooltip: tabLabel,
    displayEditToolbar: false,
    layers: [
      {
        id: K12_EQ_LAYER.p1,
        rows: [
          [
            mathInsert(L.p1.pythagorean, 'a^2+b^2=c^2'),
            mathInsert(L.p1.squareSum, '(a+b)^2=a^2+2ab+b^2', { width: 2 }),
            mathInsert(L.p1.squareDiff, '(a-b)^2=a^2-2ab+b^2', { width: 2 }),
          ],
          [
            mathInsert(L.p1.quadratic, '\\frac{-b \\pm \\sqrt{b^2-4ac}}{2a}', { width: 2 }),
            mathInsert(L.p1.diffSquares, 'a^2-b^2=(a+b)(a-b)', { width: 1.5 }),
          ],
          [
            mathInsert(L.p1.slope, 'm=\\frac{y_2-y_1}{x_2-x_1}', { width: 2 }),
            mathInsert(L.p1.distance, 'd=\\sqrt{(x_2-x_1)^2+(y_2-y_1)^2}', { width: 2 }),
          ],
          [
            mathInsert(L.p1.pointSlope, 'y-y_1=m(x-x_1)', { width: 1.5 }),
            mathInsert(L.p1.midpoint, '\\left(\\frac{x_1+x_2}{2},\\frac{y_1+y_2}{2}\\right)', { width: 2 }),
          ],
          [
            mathInsert(L.p1.ymxb, 'y=mx+b'),
            mathInsert(L.p1.yQuad, 'y=ax^2+bx+c', { width: 1.5 }),
            mathInsert(L.p1.absX, '\\left|x\\right|'),
          ],
          nav,
        ],
      },
      {
        id: K12_EQ_LAYER.p2,
        rows: [
          [
            mathInsert(L.p2.circleArea, 'A=\\pi r^2'),
            mathInsert(L.p2.circleCircum, 'C=2\\pi r'),
            mathInsert(L.p2.triHalfBh, 'A=\\frac{1}{2}bh'),
          ],
          [
            mathInsert(L.p2.rectArea, 'A=\\ell w'),
            mathInsert(L.p2.trapezoid, 'A=\\frac{1}{2}(a+b)h', { width: 1.5 }),
            mathInsert(L.p2.circleSector, 'A=\\frac{\\theta}{360^{\\circ}}\\pi r^2', { width: 2 }),
          ],
          [
            mathInsert(L.p2.prismVol, 'V=\\ell wh'),
            mathInsert(L.p2.pyramidVol, 'V=\\frac{1}{3}Bh'),
            mathInsert(L.p2.coneVol, 'V=\\frac{1}{3}\\pi r^2 h', { width: 1.5 }),
          ],
          [
            mathInsert(L.p2.sphereVol, 'V=\\frac{4}{3}\\pi r^3', { width: 1.5 }),
            mathInsert(L.p2.cylVol, 'V=\\pi r^2 h'),
            mathInsert(L.p2.sphereSA, 'SA=4\\pi r^2', { width: 1.5 }),
          ],
          [
            mathInsert(L.p2.spaceDiag3d, 'd^2=x^2+y^2+z^2', { width: 1.5 }),
            mathInsert(L.p2.rectPrismSA, 'SA=2\\ell w+2\\ell h+2wh', { width: 2 }),
          ],
          nav,
        ],
      },
      {
        id: K12_EQ_LAYER.p3,
        rows: [
          [
            mathInsert(L.p3.sin2Cos2, '\\sin^2\\theta+\\cos^2\\theta=1'),
            mathInsert(L.p3.tanDef, '\\tan\\theta=\\frac{\\sin\\theta}{\\cos\\theta}'),
          ],
          [
            mathInsert(L.p3.lawCos, 'c^2=a^2+b^2-2ab\\cos C', { width: 2 }),
            mathInsert(L.p3.lawSin, '\\frac{a}{\\sin A}=\\frac{b}{\\sin B}', { width: 2 }),
          ],
          [
            mathInsert(
              L.p3.cosSumDiff,
              '\\cos(\\alpha\\pm\\beta)=\\cos\\alpha\\cos\\beta\\mp\\sin\\alpha\\sin\\beta',
              { width: 2.0 }
            ),
          ],
          [
            mathInsert(
              L.p3.sinSumDiff,
              '\\sin(\\alpha\\pm\\beta)=\\sin\\alpha\\cos\\beta\\pm\\cos\\alpha\\sin\\beta',
              { width: 2.0 }
            ),
          ],
          [
            mathInsert(L.p3.euler, 'e^{i\\theta}=\\cos\\theta+i\\sin\\theta', { width: 2 }),
            mathInsert(L.p3.doubleAngle, '\\sin 2\\theta=2\\sin\\theta\\cos\\theta', { width: 2 }),
          ],
          nav,
        ],
      },
      {
        id: K12_EQ_LAYER.p4,
        rows: [
          [
            mathInsert(L.p4.sum1toN, '\\frac{n(n+1)}{2}'),
            mathInsert(L.p4.arithAn, 'a_n=a_1+(n-1)d', { width: 1.5 }),
            mathInsert(L.p4.geomAn, 'a_n=a_1 r^{n-1}', { width: 1.5 }),
          ],
          [
            mathInsert(L.p4.geomSum, 'S_n=a_1\\frac{1-r^n}{1-r}', { width: 2 }),
            mathInsert(L.p4.binomial, '(a+b)^n=\\sum_{k=0}^{n}\\binom{n}{k}a^{n-k}b^k', { width: 2.0 }),
          ],
          [
            mathInsert(L.p4.meanXbar, '\\bar{x}=\\frac{1}{n}\\sum_{i=1}^{n}x_i', { width: 2 }),
            mathInsert(L.p4.variance, '\\sigma^2=\\frac{1}{n}\\sum (x_i-\\mu)^2', { width: 2 }),
          ],
          [
            mathInsert(L.p4.chooseNK, '\\binom{n}{k}=\\frac{n!}{k!(n-k)!}', { width: 2 }),
            mathInsert(L.p4.permNK, 'P(n,k)=\\frac{n!}{(n-k)!}', { width: 1.5 }),
          ],
          nav,
        ],
      },
    ],
  }
}

/** Curated K-12 common chemical formulas and reaction patterns (classroom-focused). */
export function buildK12ChemFormulasVirtualKeyboardLayout(
  tabLabel: string,
  pageTooltips: K12ChemFormulasPageTooltips,
  keyLabels: K12ChemFormulasKeyLabels
): VirtualKeyboardLayout {
  const nav = k12ChemFormNavRow(pageTooltips)
  const K = keyLabels

  return {
    id: 'mindgraph-k12-chemf',
    label: tabLabel,
    tooltip: tabLabel,
    displayEditToolbar: false,
    layers: [
      {
        id: K12_CHEMF_LAYER.p1,
        rows: [
          [
            chemCe(K.p1.glucose, 'C6H12O6'),
            chemCe(K.p1.ethanol, 'C2H5OH'),
            chemCe(K.p1.acetic, 'CH3COOH'),
            chemCe(K.p1.carbonic, 'H2CO3'),
            chemCe(K.p1.calciumHydroxide, 'Ca(OH)2'),
          ],
          [
            chemCe(K.p1.kmno4, 'KMnO4'),
            chemCe(K.p1.k2cr2o7, 'K2Cr2O7'),
            chemCe(K.p1.agno3, 'AgNO3'),
            chemCe(K.p1.bacl2, 'BaCl2'),
            chemCe(K.p1.pbNitrate, 'Pb(NO3)2', { width: 1.5 }),
          ],
          [
            chemCe(K.p1.al2o3, 'Al2O3'),
            chemCe(K.p1.fe2o3, 'Fe2O3'),
            chemCe(K.p1.sio2, 'SiO2'),
            chemCe(K.p1.p4, 'P4'),
            chemCe(K.p1.s8, 'S8'),
          ],
          [
            chemCe(K.p1.nh4no3, 'NH4NO3', { width: 1.5 }),
            chemCe(K.p1.na2co3, 'Na2CO3'),
            chemCe(K.p1.kno3, 'KNO3'),
            chemCe(K.p1.mgso4, 'MgSO4'),
          ],
          nav,
        ],
      },
      {
        id: K12_CHEMF_LAYER.p2,
        rows: [
          [
            chemCe(K.p2.photosynth, '6CO2 + 6H2O -> C6H12O6 + 6O2', { width: 2 }),
            chemCe(K.p2.respiration, 'C6H12O6 + 6O2 -> 6CO2 + 6H2O', { width: 2 }),
          ],
          [
            chemCe(K.p2.rusting, '4Fe + 3O2 -> 2Fe2O3', { width: 2 }),
            chemCe(K.p2.limewater, 'CO2 + Ca(OH)2 -> CaCO3 v + H2O', { width: 2 }),
          ],
          [
            chemCe(K.p2.naWater, '2Na + 2H2O -> 2NaOH + H2', { width: 2 }),
            chemCe(K.p2.mgO2, '2Mg + O2 -> 2MgO', { width: 1.5 }),
          ],
          [
            chemCe(K.p2.nh3Synth, 'N2 + 3H2 <=> 2NH3', { width: 2 }),
            chemCe(K.p2.waterElectrolysis, '2H2O -> 2H2 + O2', { width: 2 }),
          ],
          nav,
        ],
      },
      {
        id: K12_CHEMF_LAYER.p3,
        rows: [
          [
            chemCe(K.p3.hno3, 'HNO3'),
            chemCe(K.p3.h3po4, 'H3PO4'),
            chemCe(K.p3.ch3oh, 'CH3OH'),
            chemCe(K.p3.c2h4, 'C2H4'),
            chemCe(K.p3.c2h2, 'C2H2'),
          ],
          [
            chemCe(K.p3.benzene, 'C6H6'),
            chemCe(K.p3.glucose, 'C6H12O6'),
            chemCe(K.p3.urea, 'H2NCONH2'),
            chemCe(K.p3.ammoniumNitrate, 'NH4NO3', { width: 1.5 }),
          ],
          [
            chemCe(K.p3.bleach, 'NaClO'),
            chemCe(K.p3.vinegar, 'CH3COOH'),
            chemCe(K.p3.chalk, 'CaCO3'),
            chemCe(K.p3.gypsum, 'CaSO4.2H2O', { width: 1.5 }),
          ],
          nav,
        ],
      },
    ],
  }
}

export function buildChemistryVirtualKeyboardLayout(
  tabLabel: string,
  pageTooltips: ChemistryKeyboardPageTooltips
): VirtualKeyboardLayout {
  const nav = chemNavRow(pageTooltips)

  return {
    id: 'mindgraph-chem',
    label: tabLabel,
    tooltip: tabLabel,
    displayEditToolbar: false,
    layers: [
      {
        id: CHEM_LAYER.p1,
        rows: [
          [
            chemCe('H₂O', 'H2O'),
            chemCe('CO₂', 'CO2'),
            chemCe('O₂', 'O2'),
            chemCe('N₂', 'N2'),
            chemCe('H₂', 'H2'),
            chemCe('Cl₂', 'Cl2'),
            chemCe('NH₃', 'NH3'),
            chemCe('CH₄', 'CH4'),
          ],
          [
            chemCe('→', '->'),
            chemCe('←', '<-'),
            chemCe('⇌', '<=>'),
            chemCe('↔', '<-->'),
            '+',
            chemCe('↓', 'v'),
            chemCe('↑', '^'),
          ],
          [
            chemCe('(s)', '(s)'),
            chemCe('(l)', '(l)'),
            chemCe('(g)', '(g)'),
            chemCe('(aq)', '(aq)'),
            chemCe('…', '...'),
            chemCe(',', ','),
            chemCe('*', '*'),
          ],
          [
            chemCe('2H₂+O₂', '2H2 + O2 -> 2H2O', { width: 2 }),
            chemCe('CH₄+O₂', 'CH4 + 2O2 -> CO2 + 2H2O', { width: 2 }),
            chemCe('Zn+HCl', 'Zn + 2HCl -> ZnCl2 + H2', { width: 2 }),
          ],
          nav,
        ],
      },
      {
        id: CHEM_LAYER.p2,
        rows: [
          [
            chemCe('H⁺', 'H+'),
            chemCe('OH⁻', 'OH-'),
            chemCe('Na⁺', 'Na+'),
            chemCe('Cl⁻', 'Cl-'),
            chemCe('SO₄²⁻', 'SO4^{2-}'),
            chemCe('CO₃²⁻', 'CO3^{2-}'),
            chemCe('NO₃⁻', 'NO3^{-}'),
            chemCe('NH₄⁺', 'NH4^{+}'),
          ],
          [
            chemCe('NaCl', 'NaCl'),
            chemCe('HCl', 'HCl'),
            chemCe('NaOH', 'NaOH'),
            chemCe('CaCO₃', 'CaCO3'),
            chemCe('CuSO₄·5H₂O', 'CuSO4.5H2O', { width: 1.5 }),
            chemCe('H₂SO₄', 'H2SO4'),
          ],
          [
            chemCe('Fe²⁺', 'Fe^{2+}'),
            chemCe('Fe³⁺', 'Fe^{3+}'),
            chemCe('Cu²⁺', 'Cu^{2+}'),
            chemCe('Ag⁺', 'Ag+'),
            chemCe('Ba²⁺', 'Ba^{2+}'),
            chemCe('Ca²⁺', 'Ca^{2+}'),
          ],
          nav,
        ],
      },
    ],
  }
}
