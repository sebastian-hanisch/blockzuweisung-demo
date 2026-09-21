"""PDF-Export des Ergebnisses (fpdf2, Helvetica-Kernschrift, nur Text und Tabellen).

Die Kernschriften kennen nur Latin-1: Umlaute und "×" sind erlaubt, aber "–" (Gedankenstrich), "−" (Minuszeichen), "€", "σ", "λ", "μ", "Σ", "≥", "≤", Emoji usw. lassen fpdf2 abstürzen. Deshalb läuft jeder
Text durch pdf_text(); Verfahren erscheinen mit ihren Kurznamen ohne Emoji."""

import time

import blz_constants as C
import blz_evaluation as E

_REPLACEMENTS = {
    "–": "-", "—": "-", "‑": "-", "−": "-", "Σ": "Summe", "δ": "Delta", "σ": "sigma", "λ": "lambda", "μ": "mu", "≥": ">=", "≤": "<=", "→": "->", "≈": "ca.", "€": "EUR", "·": "*",
    "“": '"', "”": '"', "„": '"', "’": "'", "‘": "'", "±": "+-", "⚠️": "(!)", "⚠": "(!)", "✅": "", "ℹ️": "", "**": "",
}


def pdf_text(text):
    """Text für die Helvetica-Kernschrift: bekannte Sonderzeichen ersetzen, den Rest Latin-1-sicher machen."""
    for old, new in _REPLACEMENTS.items():
        text = text.replace(old, new)
    return text.encode("latin-1", "replace").decode("latin-1")


def generate_blz_pdf(p, seed, res, diag, curve=None, sample=None, compress=True):
    """Ergebnis der aktuellen Einstellung als PDF: Szenario, Zusammenfassung, Verfahrensvergleich, optional Kurve und Kante, Stichprobe mit Urteil, Hinweise.

    `p`: E.Params; `res`: E.WeekResult; `diag`: E.Diagnosis; `curve`: E.Curve oder None; `sample`: Tupel von WeekRow oder None."""
    from fpdf import FPDF
    from fpdf.enums import XPos, YPos

    week = res.week
    pdf = FPDF()
    pdf.set_compression(compress)
    pdf.add_page()

    def line(text, height=7, width=0):
        pdf.cell(width, height, pdf_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def heading(text):
        pdf.set_font("Helvetica", "B", 12)
        line(text, 8)
        pdf.set_font("Helvetica", "", 10)

    def pairs(rows):
        for label, value in rows:
            pdf.cell(32, 6, pdf_text(label), border=0)
            line(value, 6)

    def table(headers, widths, rows):
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(230, 230, 230)
        for header, width in zip(headers, widths):
            pdf.cell(width, 7, pdf_text(header), border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln(7)
        pdf.set_font("Helvetica", "", 9)
        for row in rows:
            for value, width in zip(row, widths):
                pdf.cell(width, 7, pdf_text(str(value)), border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.ln(7)

    def keep_together(height):
        """Beginnt einen Abschnitt auf einer neuen Seite, wenn er sonst über den Seitenumbruch liefe (keine halb abgeschnittenen Tabellen)."""
        if pdf.get_y() + height > pdf.h - pdf.b_margin:
            pdf.add_page()

    def note(text, size=8):
        pdf.set_font("Helvetica", "I", size)
        pdf.set_text_color(110, 110, 110)
        pdf.multi_cell(0, 5, pdf_text(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(0, 0, 0)

    pdf.set_font("Helvetica", "B", 16)
    line("Blockzuweisung: In welchen Block kommen die Exportcontainer?", 10)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(120, 120, 120)
    line(f"Erstellt: {time.strftime('%d.%m.%Y %H:%M')}  -  sebastianhanisch.net", 6)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)

    heading("Szenario")
    pairs([("Woche", f"{p.ships} Schiffe, {p.blocks} Blöcke im Abstand {C.PITCH:.0f} m, {week.total} Exportcontainer"),
           ("Blockrate", f"{p.mu} Moves je Stunde und Block; Schiffe rufen bis {p.crane} Moves je Stunde ab"),
           ("Lagerplatz", f"Spitzenfüllung {p.fill} %, Grenze {week.limit:.0f} Container je Block" if week.limit is not None else "unbegrenzt"),
           ("Anlieferung", f"gleichmäßig in den {C.DELIVERY_HOURS} Stunden vor dem Beladefenster"),
           ("Verspätung", f"σ {p.sigma} h; Preis der Wartezeit λ = {p.lam} m je min"), ("Seed", str(seed))])
    pdf.ln(3)

    heading("Zusammenfassung")
    note(E.diagnosis_text(diag, p), 9)
    if diag.stock:
        note(E.stock_text(diag), 9)
    pdf.ln(2)

    heading("Verfahrensvergleich (diese Woche)")
    rows = [[C.METHOD_SHORT[o.key], f"{o.m.distance:.0f}", f"{o.m.wait:.1f}", f"{o.robust.wait:.1f}", f"{o.m.delay_max:.0f}", f"{o.m.stock_over:.0f}"] for o in res.outcomes]
    table(["Verfahren", "Weg (m)", "Wartezeit pünktlich (min)", "bei Verspätung (min)", "Beladeverzug (min)", "über Grenze"], [38, 20, 44, 36, 32, 20], rows)
    note("Wartezeit: mittlere Wartezeit je Container am Block; bei Verspätung: Mittel über 30 Szenarien mit verschobenen Beladefenstern. Beladeverzug: pünktliche Schiffe. Über Grenze: Container über der Lagergrenze.")
    pdf.ln(3)

    if curve is not None:
        keep_together(110)
        heading("Preis der Absicherung")
        table(["Preis λ (m je min)", "Weg (m)", "pünktlich (min)", "bei Verspätung (min)"], [50, 32, 40, 48],
              [[f"{pt.lam:g}", f"{pt.distance:.1f}", f"{pt.wait:.1f}", f"{pt.wait_shift:.1f}"] for pt in curve.points])
        pdf.ln(2)
        table(["erlaubte Wartezeit (min)", "kürzester Weg (m)"], [50, 50], [[str(eps), f"{d:.1f}"] for eps, d in curve.edge])
        note(f"Oben: Szenario-LP dieser Woche mit den sieben Preisen; unten: kürzester Weg bei erlaubter Wartezeit für pünktliche Schiffe (LP, ungerundet); kleinstmögliche Wartezeit {curve.min_wait:.2f} min, "
             f"Bündeln {curve.bundle_distance:.0f} m, Verteilen {curve.spread_distance:.0f} m.")
        pdf.ln(3)

    if sample is not None:
        keep_together(110)
        heading("Stichprobe und Urteil")
        srows = []
        for k in C.METHOD_KEYS:
            cells = [C.METHOD_SHORT[k]]
            for field in ("distance", "wait", "wait_shift"):
                med, lo, hi = E.spread_of(sample, k, field)
                cells.append(f"{med:.1f} [{lo:.1f}; {hi:.1f}]")
            srows.append(cells)
        table(["Verfahren", "Weg (m)", "pünktlich (min)", "bei Verspätung (min)"], [38, 44, 50, 58], srows)
        pdf.ln(2)
        pdf.set_font("Helvetica", "", 9)
        for spec in E.verdict_specs(p.lam):
            pdf.multi_cell(0, 5, pdf_text("- " + E.verdict_text(sample, *spec)[1]), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        note(f"Basis: {len(sample)} Wochen (Seeds {sample[0].seed}-{sample[-1].seed}, nicht der eingestellte Seed) mit den eingestellten Werten; Median [10. Perzentil; 90. Perzentil]. "
             "Klar heißt: Unterschied größer als zwei Standardfehler der gepaarten Differenz.")
        pdf.ln(3)

    keep_together(70)
    heading("Hinweise zum Modell")
    pdf.set_font("Helvetica", "", 9)
    for text in [
        "Flüssigkeitsmodell in Stundenschritten: Schiffe rufen ihre Container gleichmäßig über das Beladefenster ab, dieselben Container kommen gleichmäßig in den 36 Stunden vorher an und belasten den Block ebenfalls.",
        "Ein Rückstand bremst den Schiffskran nicht zurück (Untergrenze der echten Kopplung); Suchaufwand und Umstapeln im Block sind nicht modelliert: der Bündelungsvorteil ist allein der Fahrweg.",
        "Fahrweg einfach, ohne Stau; alle Blöcke gleich; Container austauschbar; der Plan wird vor der Anlieferung fest gewählt. Verspätung ist eine Verschiebung des Beladefensters, keine Dehnung.",
        "Alle Zahlen sind Größenordnungen aus einer Simulation, keine Messung an einem echten Terminal; das LP ist gegen eine unabhängige Nachrechnung und gegen vollständiges Durchprobieren geprüft.",
    ]:
        pdf.multi_cell(0, 5, pdf_text("- " + text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())
