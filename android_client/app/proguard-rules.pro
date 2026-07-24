# Keep WebSocket classes
-keep class okhttp3.** { *; }
-dontwarn okhttp3.**

# Keep Kotlin serialization
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.AnnotationsKt
-keepclassmembers class kotlinx.serialization.json.** {
    *** Companion;
}
-keepclasseswithmembers class kotlinx.serialization.json.** {
    kotlinx.serialization.KSerializer serializer(...);
}
-keep,includedescriptorclasses class com.humanaize.**$$serializer { *; }
-keepclassmembers class com.humanaize.** {
    *** Companion;
}
-keepclasseswithmembers class com.humanaize.** {
    kotlinx.serialization.KSerializer serializer(...);
}

# Keep App models
-keep class com.humanaize.aizecompanion.data.** { *; }
