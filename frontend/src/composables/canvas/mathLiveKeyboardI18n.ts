/**
 * i18n wiring for MathLive custom keyboard key labels (K-12 equations + chem formulas tabs).
 * LaTeX / \\ce{...} inserts are fixed in layout builders; only visible labels are translated.
 */
import type { K12ChemFormulasKeyLabels, K12EquationsKeyLabels } from '@/composables/canvas/mathLiveCustomKeyboardLayouts'

type TFn = (key: string) => string

const E = (t: TFn, s: string) => t(`canvas.toolbar.mathKeyboardEq${s}`)
const C = (t: TFn, s: string) => t(`canvas.toolbar.mathKeyboardChemF${s}`)

export function buildK12EquationsKeyLabels(t: TFn): K12EquationsKeyLabels {
  return {
    p1: {
      pythagorean: E(t, 'Pythagorean'),
      squareSum: E(t, 'SquareSum'),
      squareDiff: E(t, 'SquareDiff'),
      quadratic: E(t, 'Quadratic'),
      diffSquares: E(t, 'DiffSquares'),
      slope: E(t, 'Slope'),
      distance: E(t, 'Distance'),
      pointSlope: E(t, 'PointSlope'),
      midpoint: E(t, 'Midpoint'),
      ymxb: E(t, 'Ymxb'),
      yQuad: E(t, 'YQuad'),
      absX: E(t, 'AbsX'),
    },
    p2: {
      circleArea: E(t, 'CircleArea'),
      circleCircum: E(t, 'CircleCircum'),
      triHalfBh: E(t, 'TriHalfBh'),
      rectArea: E(t, 'RectArea'),
      trapezoid: E(t, 'Trapezoid'),
      circleSector: E(t, 'CircleSector'),
      prismVol: E(t, 'PrismVol'),
      pyramidVol: E(t, 'PyramidVol'),
      coneVol: E(t, 'ConeVol'),
      sphereVol: E(t, 'SphereVol'),
      cylVol: E(t, 'CylVol'),
      sphereSA: E(t, 'SphereSA'),
      spaceDiag3d: E(t, 'SpaceDiag3d'),
      rectPrismSA: E(t, 'RectPrismSA'),
    },
    p3: {
      sin2Cos2: E(t, 'Sin2Cos2'),
      tanDef: E(t, 'TanDef'),
      lawCos: E(t, 'LawCos'),
      lawSin: E(t, 'LawSin'),
      cosSumDiff: E(t, 'CosSumDiff'),
      sinSumDiff: E(t, 'SinSumDiff'),
      euler: E(t, 'Euler'),
      doubleAngle: E(t, 'DoubleAngle'),
    },
    p4: {
      sum1toN: E(t, 'Sum1toN'),
      arithAn: E(t, 'ArithAn'),
      geomAn: E(t, 'GeomAn'),
      geomSum: E(t, 'GeomSum'),
      binomial: E(t, 'Binomial'),
      meanXbar: E(t, 'MeanXbar'),
      variance: E(t, 'Variance'),
      chooseNK: E(t, 'ChooseNK'),
      permNK: E(t, 'PermNK'),
    },
  }
}

export function buildK12ChemFormulasKeyLabels(t: TFn): K12ChemFormulasKeyLabels {
  const g = C(t, 'Glucose')
  return {
    p1: {
      glucose: g,
      ethanol: C(t, 'Ethanol'),
      acetic: C(t, 'Acetic'),
      carbonic: C(t, 'Carbonic'),
      calciumHydroxide: C(t, 'CalciumHydroxide'),
      kmno4: C(t, 'Kmno4'),
      k2cr2o7: C(t, 'K2cr2o7'),
      agno3: C(t, 'Agno3'),
      bacl2: C(t, 'Bacl2'),
      pbNitrate: C(t, 'PbNitrate'),
      al2o3: C(t, 'Al2o3'),
      fe2o3: C(t, 'Fe2o3'),
      sio2: C(t, 'Sio2'),
      p4: C(t, 'P4'),
      s8: C(t, 'S8'),
      nh4no3: C(t, 'Nh4no3'),
      na2co3: C(t, 'Na2co3'),
      kno3: C(t, 'Kno3'),
      mgso4: C(t, 'Mgso4'),
    },
    p2: {
      photosynth: C(t, 'Photosynth'),
      respiration: C(t, 'Respiration'),
      rusting: C(t, 'Rusting'),
      limewater: C(t, 'Limewater'),
      naWater: C(t, 'NaWater'),
      mgO2: C(t, 'MgO2'),
      nh3Synth: C(t, 'Nh3Synth'),
      waterElectrolysis: C(t, 'WaterElectrolysis'),
    },
    p3: {
      hno3: C(t, 'Hno3'),
      h3po4: C(t, 'H3po4'),
      ch3oh: C(t, 'Ch3oh'),
      c2h4: C(t, 'C2h4'),
      c2h2: C(t, 'C2h2'),
      benzene: C(t, 'Benzene'),
      glucose: g,
      urea: C(t, 'Urea'),
      ammoniumNitrate: C(t, 'AmmoniumNitrate'),
      bleach: C(t, 'Bleach'),
      vinegar: C(t, 'Vinegar'),
      chalk: C(t, 'Chalk'),
      gypsum: C(t, 'Gypsum'),
    },
  }
}
