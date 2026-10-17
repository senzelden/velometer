"""The `/organisations` page model: each profiled body's rendered profile, the figures in the
app it stands behind (`config/organisations.yaml`, the one source -> organisation mapping) and
the plan documents it publishes (`config/plans/`), M8 spec §3."""

from velometer.app.narrative import render_organisation
from velometer.app.plans_pages import DETAIL_CITY, PROJECTS_ORG
from velometer.content.models import Organisation, OrgMapping, Source
from velometer.i18n import Lang, t
from velometer.plans.models import Plan, ReportRow


def org_of_sources(mapping: list[OrgMapping], city_id: str, profiles: set[str]) -> dict[str, str]:
    """source id -> profiled organisation id for one city (a city entry wins over `*`)."""
    out: dict[str, str] = {}
    for m in sorted(mapping, key=lambda m: m.city != "*"):  # `*` first, then the city's own
        if m.city in ("*", city_id) and m.organisation in profiles:
            out[m.source] = m.organisation
    return out


def organisations_context(
    orgs: dict[str, Organisation],
    sources: dict[str, Source],
    mapping: list[OrgMapping],
    plans: list[Plan],
    rows: list[ReportRow],
    city_names: dict[str, str],
    source_names: dict[str, str],
    lang: Lang = "en",
    fallback: dict[str, frozenset[str]] | None = None,
) -> list[dict]:
    """One entry per profile, by name: the rendered profile, its cited sources and data, the
    figures it stands behind and links to the plans it publishes or reports on. `fallback`: per
    profile id the walk paths still English on a German page."""
    out = []
    for org in sorted(orgs.values(), key=lambda o: o.name.lower()):
        doc = render_organisation(org, sources, lang, (fallback or {}).get(org.id, frozenset()))
        cited_sources, cited_refs = doc.cited(doc.sections)
        figures = sorted(  # (city's name, source's name, city id or None for every city)
            (
                t(lang, "org.all_cities") if m.city == "*" else city_names.get(m.city, m.city),
                source_names.get(m.source, m.source),
                None if m.city == "*" else m.city,
            )
            for m in mapping
            if m.organisation == org.id
        )
        plan_cities = {p.city for p in plans if p.publisher == org.id}
        plan_cities |= {
            p.city for p in plans for r in rows if r.plan_id == p.id and r.publisher == org.id
        }
        if org.id == PROJECTS_ORG:
            plan_cities.add(DETAIL_CITY)
        plan_links = [
            {
                "name": city_names.get(c, c),
                "city": c,
                "href": f"/plans/{c}" if c == DETAIL_CITY else f"/plans#{c}",
            }
            for c in sorted(plan_cities)
        ]
        out.append(
            {
                "org": org,
                "kind": t(lang, f"org.kind.{org.kind}"),
                "doc": doc,
                "cited_sources": cited_sources,
                "cited_refs": cited_refs,
                "figures": figures,
                "plans": plan_links,
            }
        )
    return out
