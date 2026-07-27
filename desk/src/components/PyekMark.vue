<template>
  <!-- PYEKMAIL brand mark: gradient peaks (that double as an envelope flap)
       over a white envelope outline. Designed for the navy sidebar / mobile
       brand bar (white envelope + bright peaks read on #1B2A4A). Matches the
       favicon / PWA icon, which uses the same geometry with a navy envelope
       on a light tile. -->
  <svg
    viewBox="106 168 310 258"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    role="img"
    aria-label="PYEKMAIL logo mark"
  >
    <defs>
      <linearGradient id="pyekMailPeak" x1="0" y1="0" x2="1" y2="0">
        <stop offset="0" stop-color="#3B82F6" />
        <stop offset="1" stop-color="#67E8F9" />
      </linearGradient>
    </defs>
    <g stroke-width="22" stroke-linejoin="round" stroke-linecap="round">
      <path
        d="M120,300 L172,222 L206,256 L256,182 L302,252 L336,220 L400,300"
        stroke="url(#pyekMailPeak)"
      />
      <path
        d="M120,300 L120,392 Q120,412 140,412 L380,412 Q400,412 400,392 L400,300"
        stroke="#ffffff"
      />
      <path d="M120,300 L256,368 L400,300" stroke="#ffffff" opacity="0.5" />
    </g>
  </svg>
</template>

<script setup lang="ts"></script>
