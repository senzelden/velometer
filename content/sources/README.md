# External source registry

Each `*.yaml` file in this directory has a top-level `sources:` list; ids must be unique across all files. A source has `id`, `publisher`, `title`, an external http(s) `url`, optional `published`, `accessed`, `language`, `kind` (official, parliament, ngo, index or press), optional `archive_url`, and `excerpts`. An excerpt is a verbatim quote of at most 60 words in the original language with a `locator`, plus `gloss_en` (an English gloss) whenever the language is not English. Full page texts are never committed.
