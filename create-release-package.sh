#!/bin/bash
#
# Copyright 2024 Sami Kiminki
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Script to create a release package.

cd "$(dirname "$0")"

# figure out the version
VERSION="$(./novelty-grinder --version | cut -d ' ' -f 2)"

ZIPNAME="releases/novelty-grinder-${VERSION}.zip"

mkdir -p releases
rm -fv "${ZIPNAME}"
zip -9vr "${ZIPNAME}" \
    LICENSE \
    README.md \
    setup-python-venv.sh \
    novelty-grinder \
    src/ \
    examples/engines.json
