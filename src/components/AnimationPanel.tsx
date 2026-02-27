import React from "react";
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
} from "react-native";

interface AnimationOption {
  id: string;
  label: string;
}

interface Props {
  animations: AnimationOption[];
  currentAnimation: string | null;
  onSelect: (id: string | null) => void;
  loading: boolean;
}

export function AnimationPanel({
  animations,
  currentAnimation,
  onSelect,
  loading,
}: Props) {
  return (
    <View style={styles.container}>
      <Text style={styles.title}>Animations</Text>
      <ScrollView horizontal showsHorizontalScrollIndicator={false}>
        <TouchableOpacity
          style={[
            styles.button,
            currentAnimation === null && styles.buttonActive,
          ]}
          onPress={() => onSelect(null)}
        >
          <Text
            style={[
              styles.buttonText,
              currentAnimation === null && styles.buttonTextActive,
            ]}
          >
            Stop
          </Text>
        </TouchableOpacity>
        {animations.map((anim) => (
          <TouchableOpacity
            key={anim.id}
            style={[
              styles.button,
              currentAnimation === anim.id && styles.buttonActive,
            ]}
            onPress={() => onSelect(anim.id)}
            disabled={loading && currentAnimation !== anim.id}
          >
            {loading && currentAnimation === anim.id ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <Text
                style={[
                  styles.buttonText,
                  currentAnimation === anim.id && styles.buttonTextActive,
                ]}
              >
                {anim.label}
              </Text>
            )}
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    backgroundColor: "#1a1a1a",
  },
  title: {
    color: "#aaa",
    fontSize: 11,
    fontWeight: "600",
    marginBottom: 6,
    textTransform: "uppercase",
    letterSpacing: 1,
  },
  button: {
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 16,
    backgroundColor: "#333",
    marginRight: 8,
    minWidth: 60,
    alignItems: "center",
  },
  buttonActive: {
    backgroundColor: "#4a90d9",
  },
  buttonText: {
    color: "#ccc",
    fontSize: 13,
    fontWeight: "500",
  },
  buttonTextActive: {
    color: "#fff",
    fontWeight: "600",
  },
});
