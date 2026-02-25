import React from "react";
import {
  ScrollView,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from "react-native";
import { MorphCategory } from "../types";
import { CategorySection } from "./CategorySection";

interface Props {
  categories: MorphCategory[];
  morphState: Record<string, number>;
  onToggleCategory: (name: string) => void;
  onValueChange: (targetName: string, value: number) => void;
  onReset: () => void;
  targetCount: number;
  meshCount: number;
}

export function MorphPanel({
  categories,
  morphState,
  onToggleCategory,
  onValueChange,
  onReset,
  targetCount,
  meshCount,
}: Props) {
  return (
    <View style={styles.container}>
      <View style={styles.toolbar}>
        <Text style={styles.title}>Morph Targets</Text>
        <Text style={styles.stats}>
          {targetCount} targets / {meshCount} meshes
        </Text>
        <TouchableOpacity style={styles.resetBtn} onPress={onReset}>
          <Text style={styles.resetText}>Reset</Text>
        </TouchableOpacity>
      </View>

      <ScrollView style={styles.scrollView} showsVerticalScrollIndicator>
        {categories.length === 0 ? (
          <View style={styles.empty}>
            <Text style={styles.emptyText}>
              No morph targets found.{"\n"}
              Load a GLB model with shape keys.
            </Text>
          </View>
        ) : (
          categories.map((cat) => (
            <CategorySection
              key={cat.name}
              category={cat}
              morphState={morphState}
              onToggle={onToggleCategory}
              onValueChange={onValueChange}
            />
          ))
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#1A1A1A",
  },
  toolbar: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: "#333",
  },
  title: {
    color: "#FFF",
    fontSize: 16,
    fontWeight: "700",
    flex: 1,
  },
  stats: {
    color: "#888",
    fontSize: 11,
    marginRight: 10,
  },
  resetBtn: {
    backgroundColor: "#C44",
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 4,
  },
  resetText: {
    color: "#FFF",
    fontSize: 12,
    fontWeight: "600",
  },
  scrollView: {
    flex: 1,
  },
  empty: {
    padding: 40,
    alignItems: "center",
  },
  emptyText: {
    color: "#888",
    fontSize: 14,
    textAlign: "center",
    lineHeight: 22,
  },
});
