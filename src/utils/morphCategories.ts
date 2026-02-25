import { CATEGORY_KEYWORDS, MorphCategory, MorphTarget } from "../types";

/**
 * Classify a morph target name into a category based on keyword matching.
 */
function classifyTarget(name: string): string {
  const lower = name.toLowerCase();

  for (const [category, keywords] of Object.entries(CATEGORY_KEYWORDS)) {
    for (const keyword of keywords) {
      if (lower.includes(keyword)) {
        return category;
      }
    }
  }

  return "Other";
}

/**
 * Given a dictionary of morph target names → indices,
 * organize them into categorized groups.
 * Pairs incr/decr targets into single bidirectional entries.
 */
export function categorizeMorphTargets(
  morphTargetDictionary: Record<string, number>,
  currentValues: Record<string, number>
): MorphCategory[] {
  const categoryMap = new Map<string, MorphTarget[]>();
  const handled = new Set<string>();

  const names = Object.keys(morphTargetDictionary);

  for (const name of names) {
    if (handled.has(name)) continue;

    const index = morphTargetDictionary[name];
    const category = classifyTarget(name);
    if (!categoryMap.has(category)) {
      categoryMap.set(category, []);
    }

    // Check for paired targets: incr/decr or up/down
    const pairPatterns: [string, string][] = [
      ["-incr", "-decr"],
      ["-up", "-down"],
    ];
    let paired = false;
    for (const [posSuffix, negSuffix] of pairPatterns) {
      if (name.endsWith(posSuffix)) {
        const base = name.slice(0, -posSuffix.length);
        const negName = base + negSuffix;
        if (negName in morphTargetDictionary) {
          handled.add(name);
          handled.add(negName);
          categoryMap.get(category)!.push({
            name: base,
            index,
            value: currentValues[name] ?? 0,
            pairedDecrIndex: morphTargetDictionary[negName],
            incrName: name,
            decrName: negName,
          });
          paired = true;
          break;
        }
      } else if (name.endsWith(negSuffix)) {
        const base = name.slice(0, -negSuffix.length);
        const posName = base + posSuffix;
        if (posName in morphTargetDictionary) {
          // Will be handled when we process the positive name
          paired = true;
          break;
        }
      }
    }

    if (!paired) {
      handled.add(name);
      categoryMap.get(category)!.push({
        name,
        index,
        value: currentValues[name] ?? 0,
      });
    }
  }

  // Sort targets within each category alphabetically
  for (const targets of categoryMap.values()) {
    targets.sort((a, b) => a.name.localeCompare(b.name));
  }

  // Build ordered category list — known categories first, "Other" last
  const orderedCategories = Object.keys(CATEGORY_KEYWORDS);
  const result: MorphCategory[] = [];

  for (const catName of orderedCategories) {
    const targets = categoryMap.get(catName);
    if (targets && targets.length > 0) {
      result.push({ name: catName, targets, expanded: false });
      categoryMap.delete(catName);
    }
  }

  // Add any remaining categories (including "Other")
  for (const [catName, targets] of categoryMap.entries()) {
    if (targets.length > 0) {
      result.push({ name: catName, targets, expanded: false });
    }
  }

  return result;
}

/**
 * Format a morph target name for display.
 * Converts "nose-width-max" → "Nose Width Max"
 */
export function formatTargetName(name: string): string {
  return name
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
