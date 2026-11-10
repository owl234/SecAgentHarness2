# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Check one installed benchmark before running adaptation and judging."""

from __future__ import annotations

import argparse

from sec_agent_harness2 import api
from sec_agent_harness2 import i18n as I18N
from sec_agent_harness2.cli import _common as C
from sec_agent_harness2.cli._common import make_adapter
from sec_agent_harness2.preflight import check


def main(argv=None):
    lang = I18N.get_lang()
    p = argparse.ArgumentParser(description=I18N.t("check.desc", lang))
    p.add_argument("--lang", default=None, choices=("en", "zh"), help=I18N.t("cell.lang", lang))
    p.add_argument("--bench", choices=C.BENCH_CHOICES, metavar="BENCH", required=True)
    p.add_argument("--subset", choices=("office", "web", "code"))
    p.add_argument("--substrate", choices=C.SUBSTRATE_CHOICES, metavar="SUBSTRATE", default="oc")
    args = p.parse_args(argv)
    lang = I18N.resolve_lang(args)
    try:
        adapter = make_adapter(args.bench, args.subset, args.substrate)
        errors = check(adapter, judge=True)
    except (OSError, RuntimeError, ValueError) as exc:
        errors = [str(exc)]
    for error in errors:
        print(I18N.t("check.fail", lang, e=error))
    if errors:
        print(I18N.t("check.incomplete", lang, n=len(errors)))
        return 1
    print(
        I18N.t("check.ready", lang, spec=adapter.spec.name, sub=args.substrate, n=len(adapter.tasks()))
    )
    print(f"  endpoint: {api.describe(_endpoint(args.substrate))}")
    return 0


def _endpoint(substrate: str):
    """The endpoint this substrate will actually contact, for the ready line."""
    return {"pi": api.pi}.get(substrate, api.opencode)()


if __name__ == "__main__":
    raise SystemExit(main())
