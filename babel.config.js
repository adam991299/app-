module.exports = function (api) {
  api.cache(true);
  return {
    presets: ['babel-preset-expo'],
    // react-native-worklets/plugin must run last (Reanimated 4 moved its
    // worklet transform out into the standalone react-native-worklets package).
    plugins: ['react-native-worklets/plugin'],
  };
};
