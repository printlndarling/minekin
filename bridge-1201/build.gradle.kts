plugins {
    alias(libs.plugins.fabric.loom)
    alias(libs.plugins.protobuf)
    `java-library`
}

// A second, independently pinned Loom project for Minecraft 1.20.1. It is a separate
// source root rather than a profile of `bridge/` because the launcher's recipe hashes
// `bridge/` as a whole into the 1.21.4 pinned `source_digest`: any file added there for
// 1.20.1 would change a reviewed digest of a build that did not change.
group = "org.minekin"
// Captured here rather than read inside the task: this build enables Gradle's
// configuration cache, and reaching for `project.version` from a task action is
// exactly what that cache refuses.
val modVersion = providers.gradleProperty("mod_version").get()
version = modVersion

base {
    archivesName = "minekin-bridge-1201"
}

dependencies {
    minecraft(libs.minecraft)
    mappings(variantOf(libs.yarn) { classifier("v2") })
    modImplementation(libs.fabric.loader)
    modImplementation(libs.fabric.api)
    implementation(libs.protobuf.javalite)
    include(libs.protobuf.javalite)
    testImplementation(platform(libs.junit.bom))
    testImplementation(libs.junit.jupiter)
    testRuntimeOnly("org.junit.platform:junit-platform-launcher")
}

sourceSets {
    main {
        proto {
            srcDir("../proto")
        }
    }
}

val protobufVersion = versionCatalogs.named("libs").findVersion("protobuf").get().requiredVersion

protobuf {
    protoc {
        artifact = "com.google.protobuf:protoc:$protobufVersion"
    }
    generateProtoTasks {
        all().configureEach {
            builtins {
                named("java") {
                    option("lite")
                }
            }
        }
    }
}

java {
    toolchain.languageVersion = JavaLanguageVersion.of(21)
    withSourcesJar()
}

// The mod's own metadata carries the version, and Fabric's template leaves a
// `${version}` placeholder for the build to fill in. Nothing filled it in, so
// the jar declared its version as the literal string "${version}" and the Loader
// warned about it on every launch: "Mod minekin_bridge uses the version
// ${version} which isn't compatible with Loader's extended semantic version
// format".
tasks.processResources {
    inputs.property("version", modVersion)
    // `expand` on the copy spec rather than inside a `filesMatching` closure:
    // this build enables the configuration cache, which cannot serialize the
    // closure Kotlin DSL would compile here. The resources are two text files.
    expand("version" to modVersion)
}

tasks.withType<JavaCompile>().configureEach {
    options.release = 17
    options.encoding = "UTF-8"
}

tasks.test {
    useJUnitPlatform()
    // The test JVM inherits this project directory as its working directory, and
    // the Minecraft log4j configuration that the `minecraft(...)` dependency puts
    // on the test classpath writes `logs/latest.log` relative to it. That landed a
    // build artifact inside `bridge/`, which is the tree `source_tree_sha256`
    // hashes — so the recipe's `source_digest` depended on whether a build had run,
    // and a checked-out tree plus a build reported "Bridge source tree digest
    // differs from the bundle recipe" for a reason that had nothing to do with the
    // source. Build output belongs under `build/`, which the digest already
    // excludes.
    workingDir = layout.buildDirectory.dir("test-working-directory").get().asFile
    // Gradle does not create a test working directory, and a process cannot be
    // started in one that does not exist.
    doFirst { workingDir.mkdirs() }
}

dependencyLocking {
    lockAllConfigurations()
}

// ---------------------------------------------------------------------------
// The host boundary's second gate
// ---------------------------------------------------------------------------

// The hosted-world control boundary contract asks for four gates, and two of them are
// over the same rule from two sides: `check_bridge_host_boundary.py` reads the sources
// and says which names a person may write, and `check_bridge_artifacts.py` reads what
// the build produced and says whether any of it reaches the server anyway — in a
// constant pool, a descriptor, the mixin configuration, the access widener, the
// entrypoint, or a packed dependency.
//
// The first runs in CI's `bridge-static` job, over a source tree. The second cannot:
// it needs the artifact, and the only place the artifact exists is where the build
// ran. So it runs here. The contract's wording for this gate is "构建必须失败", and a
// task wired into `check` is that sentence made executable rather than one more script
// a reviewer is asked to remember.
//
// The interpreter is found rather than named, and both names are tried: a bare Ubuntu
// has `python3` and no `python`, while a Windows install has `python` and often no
// `python3`. The first version of this task named `python` alone, and the container
// build this repository uses to check the jar's digest on a second platform failed with
// "A problem occurred starting process 'command 'python''" — which names neither the
// gate nor the reason. `PATH` is read through the provider API so the configuration
// cache tracks it instead of caching one machine's toolchain into the build.
fun interpreterOnPath(name: String): File? {
    val path: String = providers.environmentVariable("PATH").orNull ?: return null
    return path.split(File.pathSeparator)
        .asSequence()
        .map { File(it, name) }
        .flatMap { candidate -> sequenceOf(candidate, File(candidate.parentFile, "${candidate.name}.exe")) }
        .firstOrNull { it.isFile }
}

val namedInterpreter: String? = findProperty("gatePython") as String?
val foundInterpreter: File? = interpreterOnPath("python3") ?: interpreterOnPath("python")
val gatePython: List<String> =
    when {
        namedInterpreter != null -> namedInterpreter.split(" ").filter { it.isNotBlank() }
        foundInterpreter != null -> listOf(foundInterpreter.absolutePath)
        else -> {
            logger.warn(
                "no python3 or python on PATH: the host-boundary artifact gate cannot run, "
                    + "so `check` will fail. Name an interpreter with -PgatePython=<command>."
            )
            listOf("python3")
        }
    }
val gateArtifact = layout.buildDirectory.file("libs/minekin-bridge-1201-$modVersion.jar")
// This project is its own Gradle root — `bridge/settings.gradle.kts` — so `rootProject`
// is `bridge/` and the repository is one directory above it. Asked for as the parent of
// the project directory rather than as `..`, because a gate that walks up from wherever
// it happens to be run is how a path stops pointing at the repository.
val repositoryRoot = rootProject.layout.projectDirectory.asFile.parentFile
val gateScript = File(repositoryRoot, "tools/check_bridge_artifacts.py")
val gateNames = File(repositoryRoot, "bridge-1201/host-boundary-names.json")

val checkHostBoundaryArtifacts by tasks.registering(Exec::class) {
    group = "verification"
    description = "Refuse server state in what the compiler produced, not only in the sources"
    dependsOn(tasks.named("remapJar"))
    inputs.files(gateScript, gateNames)
    // Declared so the gate re-runs when the jar changes, and so a build that has not
    // made one yet cannot report the boundary held over an artifact that is not there.
    inputs.file(gateArtifact)
    // Resolved at configuration time: the configuration cache cannot read a provider
    // from inside a task action, which is the same reason `modVersion` is captured above.
    commandLine(
        *gatePython.toTypedArray(),
        gateScript.absolutePath,
        "--artifact",
        gateArtifact.get().asFile.absolutePath,
        "--names",
        gateNames.absolutePath,
    )
}

tasks.named("check") {
    dependsOn(checkHostBoundaryArtifacts)
}
