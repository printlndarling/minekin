package org.minekin.bridge.protocol;

import com.google.protobuf.InvalidProtocolBufferException;
import io.minekin.protocol.v1.BridgeBootstrapDescriptor;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.LinkOption;
import java.nio.file.Path;
import java.nio.file.attribute.PosixFilePermission;
import java.util.Arrays;
import java.util.Set;

/** Reads a small private protobuf descriptor exactly once and removes it before parsing. */
public final class DescriptorLoader {
    private static final long MAX_DESCRIPTOR_BYTES = 64 * 1024;
    private static final Set<PosixFilePermission> FORBIDDEN_POSIX_PERMISSIONS = Set.of(
            PosixFilePermission.GROUP_READ,
            PosixFilePermission.GROUP_WRITE,
            PosixFilePermission.GROUP_EXECUTE,
            PosixFilePermission.OTHERS_READ,
            PosixFilePermission.OTHERS_WRITE,
            PosixFilePermission.OTHERS_EXECUTE);

    private DescriptorLoader() {}

    public static BridgeBootstrapDescriptor loadAndDelete(Path descriptorPath) throws IOException {
        Path path = descriptorPath.toAbsolutePath().normalize();
        if (Files.isSymbolicLink(path)
                || !Files.isRegularFile(path, LinkOption.NOFOLLOW_LINKS)
                || Files.size(path) < 1
                || Files.size(path) > MAX_DESCRIPTOR_BYTES) {
            throw new IOException("bootstrap descriptor is missing, linked, empty, or oversized");
        }
        requirePrivatePosixPermissions(path);
        byte[] serialized = Files.readAllBytes(path);
        try {
            Files.delete(path);
            return BridgeBootstrapDescriptor.parseFrom(serialized);
        } catch (InvalidProtocolBufferException error) {
            throw new IOException("bootstrap descriptor is not valid protobuf", error);
        } finally {
            Arrays.fill(serialized, (byte) 0);
        }
    }

    private static void requirePrivatePosixPermissions(Path path) throws IOException {
        try {
            Set<PosixFilePermission> permissions = Files.getPosixFilePermissions(path);
            if (permissions.stream().anyMatch(FORBIDDEN_POSIX_PERMISSIONS::contains)) {
                throw new IOException("bootstrap descriptor permissions are not private");
            }
        } catch (UnsupportedOperationException ignored) {
            // Windows development profile relies on the private session directory ACL.
        }
    }
}
