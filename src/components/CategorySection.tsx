import React, { memo, useCallback } from "react";
import {
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import Slider from "@react-native-community/slider";
import { MorphCategory } from "../types";
import { formatTargetName } from "../utils/morphCategories";

interface Props {
  category: MorphCategory;
  morphState: Record<string, number>;
  onToggle: (name: string) => void;
  onValueChange: (targetName: string, value: number) => void;
}

// Snap to zero when within this threshold
const SNAP_THRESHOLD = 0.03;

const SliderRow = memo(function SliderRow({
  name,
  value,
  isPaired,
  onValueChange,
}: {
  name: string;
  value: number;
  isPaired: boolean;
  onValueChange: (name: string, value: number) => void;
}) {
  const minVal = isPaired ? -0.5 : 0;
  const maxVal = 0.5;

  const handleChange = useCallback(
    (v: number) => {
      // Snap to zero near center
      const snapped = Math.abs(v) < SNAP_THRESHOLD ? 0 : v;
      onValueChange(name, snapped);
    },
    [name, onValueChange]
  );

  return (
    <View style={styles.sliderRow}>
      <Text style={styles.targetName} numberOfLines={1}>
        {formatTargetName(name)}
      </Text>
      <Slider
        style={styles.slider}
        minimumValue={minVal}
        maximumValue={maxVal}
        step={0.01}
        value={value}
        onValueChange={handleChange}
        minimumTrackTintColor={isPaired ? "#666" : "#4A90D9"}
        maximumTrackTintColor={isPaired ? "#666" : "#555"}
        thumbTintColor="#4A90D9"
      />
      <Text style={styles.valueText}>{value.toFixed(2)}</Text>
    </View>
  );
});

export const CategorySection = memo(function CategorySection({
  category,
  morphState,
  onToggle,
  onValueChange,
}: Props) {
  return (
    <View style={styles.container}>
      <TouchableOpacity
        style={styles.header}
        onPress={() => onToggle(category.name)}
        activeOpacity={0.7}
      >
        <Text style={styles.arrow}>
          {category.expanded ? "\u25BC" : "\u25B6"}
        </Text>
        <Text style={styles.categoryName}>{category.name}</Text>
        <Text style={styles.count}>{category.targets.length}</Text>
      </TouchableOpacity>

      {category.expanded && (
        <View style={styles.body}>
          {category.targets.map((target) => (
            <SliderRow
              key={target.name}
              name={target.name}
              value={morphState[target.name] ?? 0}
              isPaired={target.pairedDecrIndex != null}
              onValueChange={onValueChange}
            />
          ))}
        </View>
      )}
    </View>
  );
});

const styles = StyleSheet.create({
  container: {
    marginBottom: 2,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#2A2A2A",
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 6,
  },
  arrow: {
    color: "#888",
    fontSize: 12,
    width: 20,
  },
  categoryName: {
    color: "#FFF",
    fontSize: 14,
    fontWeight: "600",
    flex: 1,
  },
  count: {
    color: "#888",
    fontSize: 12,
  },
  body: {
    backgroundColor: "#1E1E1E",
    paddingHorizontal: 8,
    paddingVertical: 4,
  },
  sliderRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 4,
  },
  targetName: {
    color: "#CCC",
    fontSize: 11,
    width: 120,
  },
  slider: {
    flex: 1,
    height: 30,
  },
  valueText: {
    color: "#888",
    fontSize: 11,
    width: 36,
    textAlign: "right",
  },
});
