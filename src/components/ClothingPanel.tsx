import React from "react";
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from "react-native";

interface ClothingOption {
  id: string;
  label: string;
}

interface ClothingPanelProps {
  tops: ClothingOption[];
  pants: ClothingOption[];
  shoes: ClothingOption[];
  selectedTop: string;
  selectedPants: string;
  selectedShoes: string;
  onSelectTop: (id: string) => void;
  onSelectPants: (id: string) => void;
  onSelectShoes: (id: string) => void;
}

function CategoryRow({
  label,
  options,
  selected,
  onSelect,
}: {
  label: string;
  options: ClothingOption[];
  selected: string;
  onSelect: (id: string) => void;
}) {
  return (
    <View style={styles.row}>
      <Text style={styles.rowLabel}>{label}</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.optionsScroll}>
        {options.map((opt) => (
          <TouchableOpacity
            key={opt.id}
            style={[styles.optionBtn, selected === opt.id && styles.optionSelected]}
            onPress={() => onSelect(opt.id)}
            activeOpacity={0.7}
          >
            <Text style={[styles.optionText, selected === opt.id && styles.optionTextSelected]}>
              {opt.label}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );
}

export function ClothingPanel({
  tops,
  pants,
  shoes,
  selectedTop,
  selectedPants,
  selectedShoes,
  onSelectTop,
  onSelectPants,
  onSelectShoes,
}: ClothingPanelProps) {
  return (
    <View style={styles.container}>
      <Text style={styles.header}>Clothing</Text>
      <CategoryRow label="Top" options={tops} selected={selectedTop} onSelect={onSelectTop} />
      <CategoryRow label="Pants" options={pants} selected={selectedPants} onSelect={onSelectPants} />
      <CategoryRow label="Shoes" options={shoes} selected={selectedShoes} onSelect={onSelectShoes} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    backgroundColor: "#1E1E1E",
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderBottomWidth: 1,
    borderBottomColor: "#333",
  },
  header: {
    color: "#FFF",
    fontSize: 14,
    fontWeight: "700",
    marginBottom: 4,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    marginVertical: 2,
  },
  rowLabel: {
    color: "#AAA",
    fontSize: 12,
    width: 42,
  },
  optionsScroll: {
    flex: 1,
  },
  optionBtn: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 12,
    backgroundColor: "#2A2A2A",
    marginRight: 6,
    borderWidth: 1,
    borderColor: "#444",
  },
  optionSelected: {
    backgroundColor: "#4A90D9",
    borderColor: "#4A90D9",
  },
  optionText: {
    color: "#CCC",
    fontSize: 11,
  },
  optionTextSelected: {
    color: "#FFF",
    fontWeight: "600",
  },
});
