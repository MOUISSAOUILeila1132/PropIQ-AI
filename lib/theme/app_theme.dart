// lib/theme/app_theme.dart
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:shared_preferences/shared_preferences.dart';

// ─────────────────────────────────────────────────────────────────────────────
//  THEME PROVIDER
// ─────────────────────────────────────────────────────────────────────────────

class ThemeProvider extends ChangeNotifier {
  static const _keyMode   = 'theme_mode';
  static const _keyAccent = 'accent_color';
  static const _keyFont   = 'font_style';

  ThemeMode    _themeMode = ThemeMode.system;
  AccentColor  _accent    = AccentColor.blue;
  AppFontStyle _font      = AppFontStyle.dmSans;

  ThemeMode    get themeMode => _themeMode;
  AccentColor  get accent    => _accent;
  AppFontStyle get font      => _font;

  // ← FIX: getters (pas des méthodes) → compatibles avec Consumer<ThemeProvider>
  ThemeData get lightTheme => AppTheme.buildLightTheme(_accent, _font);
  ThemeData get darkTheme  => AppTheme.buildDarkTheme(_accent, _font);

  ThemeProvider() {
    _load();
  }

  Future<void> _load() async {
    final prefs     = await SharedPreferences.getInstance();
    final modeIdx   = prefs.getInt(_keyMode)   ?? 0;
    final accentIdx = prefs.getInt(_keyAccent) ?? 0;
    final fontIdx   = prefs.getInt(_keyFont)   ?? 0;
    _themeMode = ThemeMode.values[modeIdx];
    _accent    = AccentColor.values[accentIdx];
    _font      = AppFontStyle.values[fontIdx];
    notifyListeners();
  }

  Future<void> setThemeMode(ThemeMode mode) async {
    _themeMode = mode;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyMode, mode.index);
  }

  Future<void> setAccent(AccentColor color) async {
    _accent = color;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyAccent, color.index);
  }

  Future<void> setFont(AppFontStyle style) async {
    _font = style;
    notifyListeners();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyFont, style.index);
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  ENUMS
// ─────────────────────────────────────────────────────────────────────────────

enum AccentColor { teal, purple, amber, red, blue, pink }

enum AppFontStyle { dmSans, playfair, syne }

// ─────────────────────────────────────────────────────────────────────────────
//  ACCENT COLOR PALETTES
// ─────────────────────────────────────────────────────────────────────────────

class AccentPalette {
  final Color primary;
  final Color primaryDark;
  final Color primaryLight;
  final Color primaryDarkBg;
  final Color swatch;

  const AccentPalette({
    required this.primary,
    required this.primaryDark,
    required this.primaryLight,
    required this.primaryDarkBg,
    required this.swatch,
  });

  static const Map<AccentColor, AccentPalette> all = {
    AccentColor.teal: AccentPalette(
      primary:       Color(0xFF14B8A6),
      primaryDark:   Color(0xFF0D9488),
      primaryLight:  Color(0xFFE0F2FE),
      primaryDarkBg: Color(0xFF0F2A28),
      swatch:        Color(0xFF14B8A6),
    ),
    AccentColor.purple: AccentPalette(
      primary:       Color(0xFF7C3AED),
      primaryDark:   Color(0xFF6D28D9),
      primaryLight:  Color(0xFFEDE9FE),
      primaryDarkBg: Color(0xFF1E1535),
      swatch:        Color(0xFF7C3AED),
    ),
    AccentColor.amber: AccentPalette(
      primary:       Color(0xFFF59E0B),
      primaryDark:   Color(0xFFD97706),
      primaryLight:  Color(0xFFFEF3C7),
      primaryDarkBg: Color(0xFF2A1F08),
      swatch:        Color(0xFFF59E0B),
    ),
    AccentColor.red: AccentPalette(
      primary:       Color(0xFFEF4444),
      primaryDark:   Color(0xFFDC2626),
      primaryLight:  Color(0xFFFEE2E2),
      primaryDarkBg: Color(0xFF2A0F0F),
      swatch:        Color(0xFFEF4444),
    ),
    AccentColor.blue: AccentPalette(
      primary:       Color(0xFF4F7FEF),   // bleu robot
      primaryDark:   Color(0xFF3B6AE0),
      primaryLight:  Color(0xFFDEEAFD),   // bleu très clair assorti fond robot
      primaryDarkBg: Color(0xFF0F1E3A),
      swatch:        Color(0xFF4F7FEF),
    ),
    AccentColor.pink: AccentPalette(
      primary:       Color(0xFFEC4899),
      primaryDark:   Color(0xFFDB2777),
      primaryLight:  Color(0xFFFDF2F8),
      primaryDarkBg: Color(0xFF2A1020),
      swatch:        Color(0xFFEC4899),
    ),
  };
}

// ─────────────────────────────────────────────────────────────────────────────
//  STATIC COLOR TOKENS
// ─────────────────────────────────────────────────────────────────────────────

class AppColors {
  // ── Accent teal par défaut (alias directs) ────────────────────────────────
  static const primary      = Color(0xFF14B8A6);
  static const primaryDark  = Color(0xFF0D9488);
  static const primaryLight = Color(0xFFE0F2FE);

  // ── Light palette ─────────────────────────────────────────────────────────
  static const lightBg      = Color(0xFFF8FAFC);
  static const lightSurface = Color(0xFFFFFFFF);
  static const lightBorder  = Color(0xFFE2E8F0);
  static const lightBorder2 = Color(0xFFCBD5E1);
  static const lightText1   = Color(0xFF1E293B);
  static const lightText2   = Color(0xFF64748B);
  static const lightText3   = Color(0xFF94A3B8);

  // ── Dark palette ──────────────────────────────────────────────────────────
  static const darkBg       = Color(0xFF0F172A);
  static const darkSurface  = Color(0xFF1E293B);
  static const darkSurface2 = Color(0xFF253047);
  static const darkBorder   = Color(0xFF1E293B);
  static const darkBorder2  = Color(0xFF334155);
  static const darkText1    = Color(0xFFF1F5F9);
  static const darkText2    = Color(0xFF94A3B8);
  static const darkText3    = Color(0xFF475569);

  // ── Semantic ──────────────────────────────────────────────────────────────
  static const success = Color(0xFF10B981);
  static const error   = Color(0xFFEF4444);
  static const warning = Color(0xFFF59E0B);

  // ── Score colors ──────────────────────────────────────────────────────────
  static const scoreSafety    = Color(0xFF10B981);
  static const scoreSchools   = Color(0xFF3B82F6);
  static const scoreTransport = Color(0xFFF59E0B);
  static const scoreAmenities = Color(0xFFEC4899);

  // ── Aliases sémantiques (auth_page, free_chat_page, history_page…) ────────
  // const → utilisables dans des TextStyle/BoxDecoration const partout.
  static const bgLight     = lightBg;      // fond de page / inputs
  static const bgDark      = lightText1;   // couleur des titres en light mode
  static const white       = lightSurface; // surface blanche
  static const borderColor = lightBorder;  // bordures génériques
  static const textMain    = lightText1;   // texte principal
  static const textMuted   = lightText2;   // texte secondaire / sous-titres
}

// ─────────────────────────────────────────────────────────────────────────────
//  FONT HELPERS
// ─────────────────────────────────────────────────────────────────────────────

class AppFonts {
  static TextStyle title(
    AppFontStyle f, {
    double size = 28,
    FontWeight weight = FontWeight.w800,
    Color? color,
  }) {
    switch (f) {
      case AppFontStyle.playfair:
        return GoogleFonts.playfairDisplay(
            fontSize: size, fontWeight: weight, color: color);
      case AppFontStyle.syne:
        return GoogleFonts.syne(
            fontSize: size, fontWeight: weight, color: color);
      case AppFontStyle.dmSans:
      default:
        return GoogleFonts.dmSans(
            fontSize: size, fontWeight: weight, color: color);
    }
  }

  static TextStyle body(
    AppFontStyle f, {
    double size = 14,
    FontWeight weight = FontWeight.w400,
    Color? color,
    double? height,
    double? letterSpacing,
  }) {
    return GoogleFonts.dmSans(
      fontSize: size,
      fontWeight: weight,
      color: color,
      height: height,
      letterSpacing: letterSpacing,
    );
  }

  static TextTheme textTheme(
      AppFontStyle f, Color mainColor, Color mutedColor) {
    TextStyle Function({
      double? fontSize,
      FontWeight? fontWeight,
      Color? color,
    }) display;

    switch (f) {
      case AppFontStyle.playfair:
        display = ({fontSize, fontWeight, color}) =>
            GoogleFonts.playfairDisplay(
                fontSize: fontSize, fontWeight: fontWeight, color: color);
        break;
      case AppFontStyle.syne:
        display = ({fontSize, fontWeight, color}) => GoogleFonts.syne(
            fontSize: fontSize, fontWeight: fontWeight, color: color);
        break;
      case AppFontStyle.dmSans:
      default:
        display = ({fontSize, fontWeight, color}) => GoogleFonts.dmSans(
            fontSize: fontSize, fontWeight: fontWeight, color: color);
    }

    return GoogleFonts.dmSansTextTheme().copyWith(
      displayLarge:
          display(fontSize: 40, fontWeight: FontWeight.w800, color: mainColor),
      displayMedium:
          display(fontSize: 32, fontWeight: FontWeight.w700, color: mainColor),
      displaySmall:
          display(fontSize: 26, fontWeight: FontWeight.w700, color: mainColor),
      headlineLarge:
          display(fontSize: 22, fontWeight: FontWeight.w700, color: mainColor),
      headlineMedium:
          display(fontSize: 18, fontWeight: FontWeight.w700, color: mainColor),
      headlineSmall:
          display(fontSize: 15, fontWeight: FontWeight.w600, color: mainColor),
      bodyLarge:  GoogleFonts.dmSans(fontSize: 16, color: mainColor),
      bodyMedium: GoogleFonts.dmSans(fontSize: 14, color: mutedColor),
      bodySmall:  GoogleFonts.dmSans(fontSize: 12, color: mutedColor),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────────────
//  THEME BUILDER
// ─────────────────────────────────────────────────────────────────────────────

class AppTheme {
  static ThemeData buildLightTheme(AccentColor accent, AppFontStyle font) {
    final p = AccentPalette.all[accent]!;
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: ColorScheme(
        brightness:       Brightness.light,
        primary:          p.primary,
        onPrimary:        Colors.white,
        secondary:        p.primaryDark,
        onSecondary:      Colors.white,
        error:            AppColors.error,
        onError:          Colors.white,
        surface:          AppColors.lightSurface,
        onSurface:        AppColors.lightText1,
        surfaceVariant:   AppColors.lightBg,
        onSurfaceVariant: AppColors.lightText2,
        outline:          AppColors.lightBorder,
      ),
      scaffoldBackgroundColor: AppColors.lightBg,
      textTheme: AppFonts.textTheme(font, AppColors.lightText1, AppColors.lightText2),
      appBarTheme: AppBarTheme(
        backgroundColor:    AppColors.lightSurface,
        foregroundColor:    AppColors.lightText1,
        elevation:          0,
        systemOverlayStyle: SystemUiOverlayStyle.dark,
        titleTextStyle:     AppFonts.title(font,
            size: 16, weight: FontWeight.w700, color: AppColors.lightText1),
        iconTheme:          const IconThemeData(color: AppColors.lightText1),
        surfaceTintColor:   Colors.transparent,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: p.primary,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(50)),
          elevation: 0,
          textStyle: AppFonts.body(font, size: 14, weight: FontWeight.w600),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: p.primary,
          side: BorderSide(color: p.primary, width: 1),
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(50)),
          textStyle: AppFonts.body(font, size: 14, weight: FontWeight.w600),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled:      true,
        fillColor:   AppColors.lightBg,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide:   const BorderSide(color: AppColors.lightBorder, width: 0.5),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide:   const BorderSide(color: AppColors.lightBorder, width: 0.5),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide:   BorderSide(color: p.primary, width: 1.5),
        ),
        hintStyle:      const TextStyle(color: AppColors.lightText3),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected) ? p.primary : Colors.white),
        trackColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected)
                ? p.primary.withOpacity(0.5)
                : AppColors.lightBorder),
      ),
      dividerColor: AppColors.lightBorder,
      dividerTheme: const DividerThemeData(
          color: AppColors.lightBorder, thickness: 0.5, space: 0),
      // ← FIX: CardTheme → CardThemeData
      cardTheme: CardThemeData(
        color:     AppColors.lightSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppColors.lightBorder, width: 0.5),
        ),
        margin: EdgeInsets.zero,
      ),
    );
  }

  static ThemeData buildDarkTheme(AccentColor accent, AppFontStyle font) {
    final p = AccentPalette.all[accent]!;
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: ColorScheme(
        brightness:       Brightness.dark,
        primary:          p.primary,
        onPrimary:        Colors.white,
        secondary:        p.primaryDark,
        onSecondary:      Colors.white,
        error:            AppColors.error,
        onError:          Colors.white,
        surface:          AppColors.darkSurface,
        onSurface:        AppColors.darkText1,
        surfaceVariant:   AppColors.darkSurface2,
        onSurfaceVariant: AppColors.darkText2,
        outline:          AppColors.darkBorder2,
      ),
      scaffoldBackgroundColor: AppColors.darkBg,
      textTheme: AppFonts.textTheme(font, AppColors.darkText1, AppColors.darkText2),
      appBarTheme: AppBarTheme(
        backgroundColor:    AppColors.darkSurface,
        foregroundColor:    AppColors.darkText1,
        elevation:          0,
        systemOverlayStyle: SystemUiOverlayStyle.light,
        titleTextStyle:     AppFonts.title(font,
            size: 16, weight: FontWeight.w700, color: AppColors.darkText1),
        iconTheme:          const IconThemeData(color: AppColors.darkText1),
        surfaceTintColor:   Colors.transparent,
      ),
      elevatedButtonTheme: ElevatedButtonThemeData(
        style: ElevatedButton.styleFrom(
          backgroundColor: p.primary,
          foregroundColor: Colors.white,
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(50)),
          elevation: 0,
          textStyle: AppFonts.body(font, size: 14, weight: FontWeight.w600),
        ),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(
          foregroundColor: p.primary,
          side: BorderSide(color: p.primary.withOpacity(0.6), width: 1),
          padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 14),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(50)),
          textStyle: AppFonts.body(font, size: 14, weight: FontWeight.w600),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled:    true,
        fillColor: AppColors.darkSurface2,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide:   const BorderSide(color: AppColors.darkBorder2, width: 0.5),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide:   const BorderSide(color: AppColors.darkBorder2, width: 0.5),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide:   BorderSide(color: p.primary, width: 1.5),
        ),
        hintStyle:      const TextStyle(color: AppColors.darkText3),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      ),
      switchTheme: SwitchThemeData(
        thumbColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected)
                ? p.primary
                : AppColors.darkText2),
        trackColor: WidgetStateProperty.resolveWith(
            (s) => s.contains(WidgetState.selected)
                ? p.primary.withOpacity(0.4)
                : AppColors.darkBorder2),
      ),
      dividerColor: AppColors.darkBorder2,
      dividerTheme: const DividerThemeData(
          color: AppColors.darkBorder2, thickness: 0.5, space: 0),
      // ← FIX: CardTheme → CardThemeData
      cardTheme: CardThemeData(
        color:     AppColors.darkSurface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: AppColors.darkBorder2, width: 0.5),
        ),
        margin: EdgeInsets.zero,
      ),
    );
  }
}
