/** 32×32 tilted claw hammer; hotspot near the strike face. */
const HAMMER_CURSOR_SVG = `<svg xmlns='http://www.w3.org/2000/svg' width='32' height='32' viewBox='0 0 32 32'>
  <g transform='rotate(-38 16 16)'>
    <rect x='14' y='15' width='5' height='14' rx='2.5' fill='%23a16207'/>
    <rect x='15' y='15' width='3' height='14' rx='1.5' fill='%23ca8a04'/>
    <rect x='5' y='5' width='18' height='11' rx='2' fill='%23334155'/>
    <rect x='5' y='5' width='8' height='11' rx='1.5' fill='%2364748b'/>
    <path d='M23 5h7v3.5l-4.5 2 4.5 2V16h-7V5z' fill='%23334155'/>
  </g>
</svg>`

export const LEARNING_SHEET_HAMMER_CURSOR = `url("data:image/svg+xml,${encodeURIComponent(
  HAMMER_CURSOR_SVG
)}") 10 8, pointer`
