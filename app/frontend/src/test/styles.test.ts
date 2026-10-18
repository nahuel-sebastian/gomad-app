/// <reference types="node" />
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

// vitest no entrega el CSS con ?raw: se lee del disco
const css = readFileSync(resolve(__dirname, "../styles/main.css"), "utf-8");

// Contraste WCAG entre dos colores #rrggbb
function luminance(hex: string): number {
    const [r, g, b] = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
    const f = (c: number) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

function contrast(a: string, b: string): number {
    const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
}

function token(name: string): string {
    const match = css.match(new RegExp(`${name}:\\s*(#[0-9a-fA-F]{6})`));
    if (!match) throw new Error(`falta el token ${name}`);
    return match[1];
}

// regla cuyo selector es exactamente `selector` (no `.padre .seg` al buscar `.seg`)
function rule(selector: string): string {
    const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    const match = new RegExp(`(?:^|\\n)\\s*${escaped} \\{`).exec(css);
    if (!match) throw new Error(`falta la regla ${selector}`);
    const start = match.index + match[0].indexOf(selector);
    return css.slice(start, css.indexOf("}", start));
}

describe("estilos", () => {
    it("las chips usan fondos suaves y texto con contraste de al menos 4,5:1", () => {
        for (const type of ["info", "nodata"]) {
            const style = rule(`.chip--${type}`);
            expect(style).toContain(`var(--chip-${type}-bg)`);
            expect(style).toContain(`var(--chip-${type}-fg)`);
            expect(contrast(token(`--chip-${type}-fg`), token(`--chip-${type}-bg`))).toBeGreaterThanOrEqual(4.5);
        }
        for (const category of ["good", "fair", "moderate", "poor", "very_poor", "extremely_poor", "nodata"]) {
            const palette = `aqi-${category.replaceAll("_", "-")}`;
            const style = rule(`.chip--aqi-${category}`);
            expect(style).toContain(`var(--chip-${palette}-bg)`);
            expect(style).toContain(`var(--chip-${palette}-fg)`);
            expect(contrast(token(`--chip-${palette}-fg`), token(`--chip-${palette}-bg`))).toBeGreaterThanOrEqual(4.5);
        }
    });

    it("--border-strong tiene al menos 3:1 sobre la superficie y el fondo (WCAG 1.4.11)", () => {
        const border = token("--border-strong");
        expect(contrast(border, token("--surface"))).toBeGreaterThanOrEqual(3);
        expect(contrast(border, token("--bg"))).toBeGreaterThanOrEqual(3);
    });

    it("los bordes de opciones, segmentos, candidatos y el boton discreto usan --border-strong", () => {
        for (const selector of [".option", ".seg", ".candidate", ".button--quiet"]) {
            expect(rule(selector)).toMatch(/var\(--border-strong\)/);
        }
    });

    it("un boton con aria-disabled se ve deshabilitado sin bajar el texto de 4,5:1", () => {
        const disabled = rule('.button[aria-disabled="true"]');
        expect(disabled).toMatch(/cursor:\s*not-allowed/);
        expect(disabled).not.toMatch(/opacity/);
        const fg = disabled.match(/\n\s*color:\s*var\((--[\w-]+)\)/)?.[1];
        const bg = disabled.match(/\n\s*background:\s*var\((--[\w-]+)\)/)?.[1];
        expect(fg && bg).toBeTruthy();
        expect(contrast(token(fg!), token(bg!))).toBeGreaterThanOrEqual(4.5);
    });
});

describe("css muerto", () => {
    it("no quedan reglas de los filtros quitados (.filter-chip, .results-filter-chips)", () => {
        expect(css).not.toMatch(/\.filter-chip\b|\.results-filter-chips\b/);
    });
});

describe("barra de navegacion inferior", () => {
    it("en movil las paginas dejan sitio a la barra inferior fija", () => {
        // la barra inferior es fixed: sin este hueco tapa el ultimo boton (p. ej. «Buscar actividad en…»)
        const mobile = css.split("@media (max-width: 47.9375rem)").slice(1);
        expect(
            mobile.some((block) =>
                /\.page \{[^}]*padding-bottom:\s*calc\([^;]*var\(--bottom-nav-height\)/.test(block.split("\n}\n")[0]),
            ),
        ).toBe(true);
    });
});
