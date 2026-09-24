package org.minekin.bridge.protocol;

import io.minekin.protocol.v1.EndpointTransport;
import io.minekin.protocol.v1.IpcEndpoint;
import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.ProtocolFamily;
import java.net.StandardProtocolFamily;
import java.net.UnixDomainSocketAddress;
import java.nio.channels.SelectionKey;
import java.nio.channels.Selector;
import java.nio.channels.SocketChannel;
import java.time.Duration;

/** Opens only the local endpoint forms accepted by the bootstrap adapter. */
public final class EndpointConnector {
    private EndpointConnector() {}

    public static SocketChannel connect(IpcEndpoint endpoint, Duration timeout) throws IOException {
        long deadline = deadline(timeout);
        ProtocolFamily family;
        java.net.SocketAddress address;
        if (endpoint.getTransport() == EndpointTransport.ENDPOINT_TRANSPORT_LOOPBACK_TCP
                && "127.0.0.1".equals(endpoint.getHost())
                && endpoint.getPort() > 0
                && endpoint.getPort() <= 65535) {
            family = StandardProtocolFamily.INET;
            address = new InetSocketAddress(endpoint.getHost(), endpoint.getPort());
        } else if (endpoint.getTransport()
                        == EndpointTransport.ENDPOINT_TRANSPORT_UNIX_DOMAIN_SOCKET
                && !endpoint.getUnixSocketPath().isBlank()) {
            family = StandardProtocolFamily.UNIX;
            address = UnixDomainSocketAddress.of(endpoint.getUnixSocketPath());
        } else {
            throw new IllegalArgumentException("endpoint is not a reviewed local transport");
        }

        SocketChannel socket = SocketChannel.open(family);
        boolean connected = false;
        try {
            socket.configureBlocking(false);
            if (!socket.connect(address)) {
                try (Selector selector = Selector.open()) {
                    socket.register(selector, SelectionKey.OP_CONNECT);
                    while (!socket.finishConnect()) {
                        await(selector, deadline, "IPC connect timed out");
                    }
                }
            }
            connected = true;
            return socket;
        } finally {
            if (!connected) {
                socket.close();
            }
        }
    }

    static long deadline(Duration timeout) {
        if (timeout == null || timeout.isZero() || timeout.isNegative()) {
            throw new IllegalArgumentException("IPC timeout must be positive");
        }
        try {
            return System.nanoTime() + timeout.toNanos();
        } catch (ArithmeticException error) {
            throw new IllegalArgumentException("IPC timeout is too large", error);
        }
    }

    static void await(Selector selector, long deadline, String message) throws IOException {
        while (true) {
            if (Thread.currentThread().isInterrupted()) {
                throw new IOException("IPC operation interrupted");
            }
            long remaining = deadline - System.nanoTime();
            if (remaining <= 0) {
                throw new java.net.SocketTimeoutException(message);
            }
            long millis = Math.max(1, Math.min(remaining / 1_000_000, Integer.MAX_VALUE));
            if (selector.select(millis) > 0) {
                selector.selectedKeys().clear();
                return;
            }
        }
    }
}
