package org.minekin.bridge.runtime;

import com.google.protobuf.ByteString;
import io.minekin.protocol.v1.AimInput;
import io.minekin.protocol.v1.ActionResult;
import io.minekin.protocol.v1.ActionStatus;
import io.minekin.protocol.v1.AdmissionFailureReason;
import io.minekin.protocol.v1.BridgeBootstrapDescriptor;
import io.minekin.protocol.v1.CallbackBudgetWindow;
import io.minekin.protocol.v1.CancelConnection;
import io.minekin.protocol.v1.Channel;
import io.minekin.protocol.v1.ConnectWorld;
import io.minekin.protocol.v1.ConnectionLifecycle;
import io.minekin.protocol.v1.ConnectionPhase;
import io.minekin.protocol.v1.CoreHello;
import io.minekin.protocol.v1.Envelope;
import io.minekin.protocol.v1.GuiClickInput;
import io.minekin.protocol.v1.GuiRecipeClick;
import io.minekin.protocol.v1.GuiSlotClick;
import io.minekin.protocol.v1.Heartbeat;
import io.minekin.protocol.v1.HotbarSelectInput;
import io.minekin.protocol.v1.HostLifecycle;
import io.minekin.protocol.v1.HostPhase;
import io.minekin.protocol.v1.InitialObservation;
import io.minekin.protocol.v1.LookInput;
import io.minekin.protocol.v1.MineInput;
import io.minekin.protocol.v1.MoveInput;
import io.minekin.protocol.v1.OpenLan;
import io.minekin.protocol.v1.ProtocolVersion;
import io.minekin.protocol.v1.ReleaseAllInputs;
import io.minekin.protocol.v1.ResourcePackPolicy;
import io.minekin.protocol.v1.ScreenInput;
import io.minekin.protocol.v1.UseInput;
import io.minekin.protocol.v1.WorldObservation;
import java.io.IOException;
import java.net.SocketTimeoutException;
import java.nio.channels.SocketChannel;
import java.nio.file.Path;
import java.time.Duration;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.function.Consumer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.minekin.bridge.action.WorldActions;
import org.minekin.bridge.action.WorldClientView;
import org.minekin.bridge.protocol.AdmissionCommandGate;
import org.minekin.bridge.protocol.BootstrapDescriptorAdapter;
import org.minekin.bridge.protocol.DescriptorLoader;
import org.minekin.bridge.protocol.EndpointConnector;
import org.minekin.bridge.protocol.EnvelopeGate;
import org.minekin.bridge.protocol.HandshakeGate;
import org.minekin.bridge.input.BridgeInputController;
import org.minekin.bridge.input.InputWatchdog;
import org.minekin.bridge.input.KeySink;
import org.minekin.bridge.input.ViewSink;
import org.minekin.bridge.protocol.NioEnvelopeChannel;

/** Owns descriptor I/O, both local sockets, protobuf encoding, and handshake on a daemon thread. */
public final class BridgeIpcWorker implements AutoCloseable {
    public static final String BRIDGE_HELLO_TYPE = "minekin.v1.BridgeHello";
    public static final String CORE_HELLO_TYPE = "minekin.v1.CoreHello";
    public static final String HEARTBEAT_TYPE = "minekin.v1.Heartbeat";
    public static final String CONNECT_WORLD_TYPE = "minekin.v1.ConnectWorld";
    public static final String CANCEL_CONNECTION_TYPE = "minekin.v1.CancelConnection";
    public static final String CONNECTION_LIFECYCLE_TYPE = "minekin.v1.ConnectionLifecycle";
    public static final String RELEASE_ALL_INPUTS_TYPE = "minekin.v1.ReleaseAllInputs";
    public static final String INITIAL_OBSERVATION_TYPE = "minekin.v1.InitialObservation";
    public static final String MOVE_INPUT_TYPE = "minekin.v1.MoveInput";
    public static final String LOOK_INPUT_TYPE = "minekin.v1.LookInput";
    public static final String USE_INPUT_TYPE = "minekin.v1.UseInput";
    public static final String ACTION_RESULT_TYPE = "minekin.v1.ActionResult";
    public static final String OPEN_LAN_TYPE = "minekin.v1.OpenLan";
    public static final String HOST_LIFECYCLE_TYPE = "minekin.v1.HostLifecycle";
    public static final String BUDGET_WINDOW_TYPE = "minekin.v1.CallbackBudgetWindow";
    // S2's five inbound action types and its one recurring observation type, spelled the
    // way the wire names them. Each is gated by its own capability before it is queued, and
    // refused by name (`CAPABILITY_NOT_GRANTED`) rather than fail-closed when that capability
    // was never negotiated — the mistake is Core's to see, and a named code in the reply is
    // where it becomes visible instead of a stopped client.
    public static final String AIM_INPUT_TYPE = "minekin.v1.AimInput";
    public static final String MINE_INPUT_TYPE = "minekin.v1.MineInput";
    public static final String HOTBAR_SELECT_INPUT_TYPE = "minekin.v1.HotbarSelectInput";
    public static final String SCREEN_INPUT_TYPE = "minekin.v1.ScreenInput";
    public static final String GUI_CLICK_INPUT_TYPE = "minekin.v1.GuiClickInput";
    public static final String WORLD_OBSERVATION_TYPE = "minekin.v1.WorldObservation";
    private static final Logger LOGGER = LoggerFactory.getLogger("minekin-bridge");
    /**
     * How many heartbeat intervals of silence the Bridge tolerates before it lets go of
     * the player's controls. More than one, because a single missed interval is ordinary
     * scheduling jitter rather than a reason to stop walking.
     */
    static final int INPUT_MISSED_HEARTBEATS = 3;
    /**
     * How many heartbeat intervals of silence mean the channel is gone rather than
     * its peer being slow.
     *
     * <p>Deliberately far longer than the input watchdog tolerates, and the reason
     * is the one measurement that matters here: at the same tolerance the release
     * never happens, because stopping the client wins the race. Measured on the
     * controlled runner — two seconds of SIGSTOP on Core while the Kin walked
     * produced `bridge is failing closed` and a stopped client, not the
     * `bridge released 1 input(s) after TIMEOUT` the contract asks for.
     *
     * <p>Letting go of the keys is the first response to silence; stopping the
     * client destroys a session that a returning Core may still own, so it waits
     * for silence no scheduling hiccup could produce.
     */
    static final int CORE_ABSENT_INTERVALS = 60;
    private static final long MONOTONIC_ORIGIN = System.nanoTime();

    private final Path descriptorPath;
    private final ClientRuntimeIdentity identity;
    private final Duration connectTimeout;
    private final Duration handshakeTimeout;
    private final BridgePhaseMachine phases;
    private final KeySink keySink;
    private final ViewSink viewSink;
    private final BoundedChannel<ClientMessage> clientInbox;
    private final BoundedChannel<EventMessage> eventOutbox;
    private final AdmissionCommandGate admissionCommands = new AdmissionCommandGate();
    private final AtomicBoolean started = new AtomicBoolean();
    private final AtomicBoolean stopping = new AtomicBoolean();
    private volatile Thread thread;
    private volatile Thread eventThread;
    private volatile NioEnvelopeChannel control;
    private volatile NioEnvelopeChannel event;
    /** Why the Bridge is failing closed, for the release that follows it. */
    private volatile BridgeInputController.ReleaseReason faultReason =
            BridgeInputController.ReleaseReason.BRIDGE_FAULT;
    private volatile BridgeInputController input;
    /**
     * The capabilities Core accepted at handshake, kept for the whole session.
     *
     * <p>Read on two threads: the heartbeat loop refuses an inbound action whose capability
     * is not here, and the client tick asks whether the recurring observation is granted
     * before it spends a tick reading the world. Both read the same immutable snapshot Core
     * agreed to, so the field is volatile and its value a {@link Set} copied at handshake.
     */
    private volatile Set<String> negotiatedCapabilities = Set.of();
    /** The generation this session answers for, so an observation names the right one. */
    private volatile long sessionGeneration;
    /**
     * The Minecraft side of the S2 actions, injected from the client entrypoint.
     *
     * <p>The worker owns sockets, decisions and the lease ledger and holds no Minecraft type;
     * this is the one seam through which an applied command reads a crosshair, writes a slot,
     * or taps a key. It is attached before {@link #start()} and read only on the client tick.
     */
    private volatile WorldClientView worldView;

    public BridgeIpcWorker(
            Path descriptorPath,
            ClientRuntimeIdentity identity,
            Duration connectTimeout,
            Duration handshakeTimeout,
            int inboxCapacity,
            BridgePhaseMachine phases,
            KeySink keySink,
            ViewSink viewSink) {
        this.descriptorPath = descriptorPath.toAbsolutePath().normalize();
        this.identity = java.util.Objects.requireNonNull(identity, "identity");
        this.connectTimeout = requirePositive(connectTimeout, "connectTimeout");
        this.handshakeTimeout = requirePositive(handshakeTimeout, "handshakeTimeout");
        this.phases = java.util.Objects.requireNonNull(phases, "phases");
        this.keySink = java.util.Objects.requireNonNull(keySink, "keySink");
        this.viewSink = java.util.Objects.requireNonNull(viewSink, "viewSink");
        clientInbox = new BoundedChannel<>(inboxCapacity);
        eventOutbox = new BoundedChannel<>(inboxCapacity);
    }

    /** Starts exactly once and returns without descriptor or socket I/O. */
    public void start() {
        if (!started.compareAndSet(false, true)) {
            throw new IllegalStateException("Bridge IPC worker already started");
        }
        Thread worker = new Thread(this::run, "minekin-bridge-ipc");
        worker.setDaemon(true);
        thread = worker;
        worker.start();
    }

    public int drainClientMessages(int limit, Consumer<ClientMessage> consumer) {
        return clientInbox.drain(limit, consumer);
    }

    public BridgePhaseMachine.Phase phase() {
        return phases.phase();
    }

    /**
     * Whether Core negotiated a capability for this session.
     *
     * <p>False until the handshake records what was accepted, so a client tick that runs
     * before activation asks a question with a clear answer rather than a null set.
     */
    public boolean hasCapability(String capability) {
        return negotiatedCapabilities.contains(capability);
    }

    /** The generation a recurring observation must name, and 0 before one is negotiated. */
    public long sessionGeneration() {
        return sessionGeneration;
    }

    /**
     * Attaches the Minecraft half the S2 actions are applied through.
     *
     * <p>Called from the client entrypoint before {@link #start()}. The worker keeps the seam
     * behind an interface precisely so it can be tested with the socket, lease and result
     * logic exercised and no running game on the other side of it.
     */
    public void attachWorldView(WorldClientView worldView) {
        this.worldView = java.util.Objects.requireNonNull(worldView, "worldView");
    }

    /**
     * The watchdog's clock, driven from the client thread.
     *
     * <p>The heartbeat loop already refuses to wait forever for Core, and this is
     * the other failure: a worker thread that is itself wedged, which no loop can
     * notice. The client thread is still ticking when that happens, and this is
     * what it does about it. Returns true on the tick that let go.
     */
    public boolean tickInput() {
        BridgeInputController controller = input;
        boolean released = controller != null && controller.tick(monotonicNow());
        if (released) {
            LOGGER.warn("bridge released input after {}", BridgeInputController.ReleaseReason.TIMEOUT);
        }
        return released;
    }

    /**
     * Turns the view the command asks for, and answers for it.

     * <p>One turn, applied and over: nothing is held afterwards, so there is
     * nothing here for a release to lift. The answer matters for the same reason
     * it does for a movement command — a Kin that was told to look and did not is
     * a fact Core has to be able to record.
     */
    private void applyLook(LookInput command) {
        BridgeInputController controller = input;
        if (controller == null) {
            return;
        }
        BridgeInputController.Outcome outcome = controller.look(
                monotonicNow(),
                command.getDeadlineMonotonicNs(),
                command.getGeneration(),
                command.getDeltaYawDegrees(),
                command.getDeltaPitchDegrees());
        if (outcome.applied()) {
            LOGGER.info(
                    "bridge applied look {}: {} yaw, {} pitch degrees",
                    command.getActionId(),
                    command.getDeltaYawDegrees(),
                    command.getDeltaPitchDegrees());
        } else {
            LOGGER.warn(
                    "bridge refused look {}: {}", command.getActionId(), outcome.refusalCode());
        }
        publishActionResult(
                ActionResult.newBuilder()
                        .setActionId(command.getActionId())
                        .setGeneration(command.getGeneration())
                        .setStatus(
                                outcome.applied()
                                        ? ActionStatus.ACTION_STATUS_ACCEPTED
                                        : ActionStatus.ACTION_STATUS_FAILED)
                        .setReasonCode(outcome.refusalCode())
                        .build());
    }

    /**
     * What the client is showing, from the client tick.
     *
     * <p>The keyboard's owner is the one release trigger only this side can see, so it
     * arrives as an observation rather than as a question: this class owns the
     * sockets and knows nothing about screens, and the client tick knows nothing
     * about leases. An empty label means the client is taking input again.
     */
    public void observeClientInput(String openScreen) {
        BridgeInputController controller = input;
        if (controller == null) {
            return;
        }
        if (openScreen.isEmpty()) {
            controller.unblockInput();
            return;
        }
        if (controller.blockInput(openScreen)) {
            LOGGER.warn("bridge let go of its held input: the client is showing {}", openScreen);
        }
    }

    /** Apply an input-side client message synchronously on the client tick. */
    public boolean handleInputMessage(ClientMessage message) {
        java.util.Objects.requireNonNull(message, "message");
        if (message instanceof ReleaseCommand release) {
            releaseInputs(
                    BridgeInputController.ReleaseReason.CORE_REQUEST,
                    release.value().getReasonCode());
            return true;
        }
        if (message instanceof MoveCommand move) {
            applyMove(move.value());
            return true;
        }
        if (message instanceof LookCommand look) {
            applyLook(look.value());
            return true;
        }
        if (message instanceof UseCommand use) {
            applyUse(use.value());
            return true;
        }
        if (message instanceof AimCommand aim) {
            applyAim(aim);
            return true;
        }
        if (message instanceof MineCommand mine) {
            applyMine(mine);
            return true;
        }
        if (message instanceof HotbarSelectCommand hotbar) {
            applyHotbar(hotbar);
            return true;
        }
        if (message instanceof ScreenCommand screen) {
            applyScreen(screen);
            return true;
        }
        if (message instanceof GuiClickCommand gui) {
            applyGui(gui);
            return true;
        }
        if (message == Notice.SAFE_STOP) {
            // The reason the worker failed closed with, not a default: this notice is
            // how a fault reaches the client thread, and the release it triggers is the
            // one an operator will read.
            releaseInputs(faultReason, "");
        }
        return false;
    }

    /**
     * Presses and lifts the keys the command asks for, and answers for it.
     *
     * <p>Every command gets an answer, refused ones included. A Kin that was told
     * to walk and did not is a fact Core has to be able to record, and the
     * alternative — silence — reads exactly like a command that is still being
     * carried out.
     */
    private void applyMove(MoveInput command) {
        BridgeInputController controller = input;
        if (controller == null) {
            return;
        }
        BridgeInputController.Outcome outcome = controller.move(
                monotonicNow(),
                command.getDeadlineMonotonicNs(),
                command.getGeneration(),
                command.getForward(),
                command.getStrafe(),
                command.getJump(),
                command.getSneak());
        if (outcome.applied()) {
            LOGGER.info("bridge applied {}: holding {}", command.getActionId(), outcome.held());
        } else {
            LOGGER.warn(
                    "bridge refused {}: {} (holding {})",
                    command.getActionId(),
                    outcome.refusalCode(),
                    outcome.held());
        }
        publishActionResult(
                ActionResult.newBuilder()
                        .setActionId(command.getActionId())
                        .setGeneration(command.getGeneration())
                        .setStatus(
                                outcome.applied()
                                        ? ActionStatus.ACTION_STATUS_ACCEPTED
                                        : ActionStatus.ACTION_STATUS_FAILED)
                        .setReasonCode(outcome.refusalCode())
                        .build());
    }

    private void applyUse(UseInput command) {
        BridgeInputController controller = input;
        if (controller == null) {
            return;
        }
        BridgeInputController.Outcome outcome = controller.use(
                monotonicNow(),
                command.getDeadlineMonotonicNs(),
                command.getGeneration(),
                command.getUse());
        if (outcome.applied()) {
            LOGGER.info("bridge applied {}: holding {}", command.getActionId(), outcome.held());
        } else {
            LOGGER.warn(
                    "bridge refused {}: {} (holding {})",
                    command.getActionId(),
                    outcome.refusalCode(),
                    outcome.held());
        }
        publishActionResult(
                ActionResult.newBuilder()
                        .setActionId(command.getActionId())
                        .setGeneration(command.getGeneration())
                        .setStatus(
                                outcome.applied()
                                        ? ActionStatus.ACTION_STATUS_ACCEPTED
                                        : ActionStatus.ACTION_STATUS_FAILED)
                        .setReasonCode(outcome.refusalCode())
                        .build());
    }

    /**
     * Turns the view one clamped step toward an absolute heading, and answers for it.
     *
     * <p>The clamp and the "is the heading reached yet" decision are the controller's and the
     * arithmetic is {@link WorldActions}'s; this method only supplies the two facts neither
     * can know — the client's angles this instant (read through the world view) and the result
     * status Core reads back. A turn that has more movement owed reports {@code STARTED} with
     * the {@code AIM_IN_PROGRESS} signal, never a {@code SUCCEEDED} it did not earn, because a
     * snapped heading is exactly the teleport the clamp exists to forbid and a reader would
     * otherwise see a completed turn that was a jump.
     */
    private void applyAim(AimCommand command) {
        BridgeInputController controller = input;
        if (controller == null) {
            return;
        }
        AimInput value = command.value();
        WorldClientView view = worldView;
        WorldActions.LookAngles angles = view == null ? null : view.lookAngles();
        if (angles == null) {
            publishResult(
                    value.getActionId(),
                    value.getGeneration(),
                    ActionStatus.ACTION_STATUS_FAILED,
                    WorldActions.REFUSED_NOT_IN_WORLD);
            LOGGER.warn("bridge refused aim {}: {}", value.getActionId(), WorldActions.REFUSED_NOT_IN_WORLD);
            return;
        }
        BridgeInputController.AimOutcome outcome =
                controller.aim(
                        monotonicNow(),
                        command.deadlineNanos(),
                        value.getGeneration(),
                        angles.yawDegrees(),
                        angles.pitchDegrees(),
                        value.getYawDegrees(),
                        value.getPitchDegrees());
        if (!outcome.applied()) {
            publishResult(
                    value.getActionId(),
                    value.getGeneration(),
                    ActionStatus.ACTION_STATUS_FAILED,
                    outcome.refusalCode());
            LOGGER.warn("bridge refused aim {}: {}", value.getActionId(), outcome.refusalCode());
            return;
        }
        if (outcome.inProgress()) {
            publishResult(
                    value.getActionId(),
                    value.getGeneration(),
                    ActionStatus.ACTION_STATUS_STARTED,
                    WorldActions.AIM_IN_PROGRESS);
            LOGGER.info("bridge stepped aim {} toward {}°/{}°", value.getActionId(),
                    value.getYawDegrees(), value.getPitchDegrees());
        } else {
            publishResult(
                    value.getActionId(),
                    value.getGeneration(),
                    ActionStatus.ACTION_STATUS_SUCCEEDED,
                    "");
            LOGGER.info("bridge reached aim {} at {}°/{}°", value.getActionId(),
                    value.getYawDegrees(), value.getPitchDegrees());
        }
    }

    /**
     * Holds the attack key to mine, or lets it go, and answers for it.
     *
     * <p>The lease guard runs first (a stale or deadlined command is refused the same way a
     * movement command is), and only then is the target checked against the client's own
     * crosshair — a command for a block the client has since looked away from is refused by
     * name ({@code MINE_TARGET_NOT_AIMED}) rather than breaking whatever is now in front of
     * it. Starting a break reports {@code STARTED} and not {@code SUCCEEDED}: the bridge holds
     * the key at the client's own pace and whether the block actually fell is a fact the next
     * {@code WorldObservation} records, not one the press of a key can claim.
     */
    private void applyMine(MineCommand command) {
        BridgeInputController controller = input;
        if (controller == null) {
            return;
        }
        MineInput value = command.value();
        boolean mining = value.getMining();
        WorldClientView view = worldView;
        if (mining) {
            BridgeInputController.Outcome guard =
                    controller.preflight(
                            monotonicNow(),
                            command.deadlineNanos(),
                            value.getGeneration(),
                            true);
            if (!guard.applied()) {
                publishResult(
                        value.getActionId(),
                        value.getGeneration(),
                        ActionStatus.ACTION_STATUS_FAILED,
                        guard.refusalCode());
                LOGGER.warn("bridge refused mine {}: {}", value.getActionId(), guard.refusalCode());
                return;
            }
            if (view == null || !view.inWorld()) {
                publishResult(
                        value.getActionId(),
                        value.getGeneration(),
                        ActionStatus.ACTION_STATUS_FAILED,
                        WorldActions.REFUSED_NOT_IN_WORLD);
                LOGGER.warn(
                        "bridge refused mine {}: {}",
                        value.getActionId(),
                        WorldActions.REFUSED_NOT_IN_WORLD);
                return;
            }
            Optional<String> refusal =
                    WorldActions.mineTargetRefusal(value.getTarget(), view.crosshair());
            if (refusal.isPresent()) {
                publishResult(
                        value.getActionId(),
                        value.getGeneration(),
                        ActionStatus.ACTION_STATUS_FAILED,
                        refusal.get());
                LOGGER.warn("bridge refused mine {}: {}", value.getActionId(), refusal.get());
                return;
            }
        }
        BridgeInputController.Outcome outcome =
                controller.mine(
                        monotonicNow(),
                        command.deadlineNanos(),
                        value.getGeneration(),
                        mining);
        if (!outcome.applied()) {
            publishResult(
                    value.getActionId(),
                    value.getGeneration(),
                    ActionStatus.ACTION_STATUS_FAILED,
                    outcome.refusalCode());
            LOGGER.warn("bridge refused mine {}: {}", value.getActionId(), outcome.refusalCode());
            return;
        }
        publishResult(
                value.getActionId(),
                value.getGeneration(),
                mining ? ActionStatus.ACTION_STATUS_STARTED : ActionStatus.ACTION_STATUS_ACCEPTED,
                "");
        LOGGER.info("bridge applied mine {} (mining={})", value.getActionId(), mining);
    }

    /**
     * Puts a hotbar slot in hand, and answers for it.
     *
     * <p>Guarded like gameplay (a screen owning the keyboard refuses it), then range-checked
     * by {@link WorldActions} against the nine the message may name, then written through the
     * world view. {@code ACCEPTED} rather than {@code SUCCEEDED}: writing the held slot is the
     * input, and that the hand now holds the intended stack is a reading the next observation's
     * {@code selected_slot} confirms.
     */
    private void applyHotbar(HotbarSelectCommand command) {
        BridgeInputController controller = input;
        if (controller == null) {
            return;
        }
        HotbarSelectInput value = command.value();
        BridgeInputController.Outcome guard =
                controller.preflight(
                        monotonicNow(), command.deadlineNanos(), value.getGeneration(), true);
        if (!guard.applied()) {
            publishResult(
                    value.getActionId(),
                    value.getGeneration(),
                    ActionStatus.ACTION_STATUS_FAILED,
                    guard.refusalCode());
            LOGGER.warn("bridge refused hotbar {}: {}", value.getActionId(), guard.refusalCode());
            return;
        }
        Optional<String> refusal = WorldActions.hotbarRefusal(value.getSlot());
        if (refusal.isPresent()) {
            publishResult(
                    value.getActionId(),
                    value.getGeneration(),
                    ActionStatus.ACTION_STATUS_FAILED,
                    refusal.get());
            LOGGER.warn("bridge refused hotbar {}: {}", value.getActionId(), refusal.get());
            return;
        }
        WorldClientView view = worldView;
        if (view == null || !view.selectHotbar(value.getSlot())) {
            publishResult(
                    value.getActionId(),
                    value.getGeneration(),
                    ActionStatus.ACTION_STATUS_FAILED,
                    WorldActions.REFUSED_NOT_IN_WORLD);
            LOGGER.warn(
                    "bridge refused hotbar {}: {}", value.getActionId(), WorldActions.REFUSED_NOT_IN_WORLD);
            return;
        }
        publishResult(
                value.getActionId(), value.getGeneration(), ActionStatus.ACTION_STATUS_ACCEPTED, "");
    }

    /**
     * Opens or closes a screen, and answers for it.
     *
     * <p>The two directions share the lease guard but not the keyboard rule: opening the
     * player's inventory is gameplay and a screen already holding the keyboard refuses it,
     * while closing is about the screen itself, so a screen is its precondition rather than a
     * reason to refuse. {@code OPEN_INVENTORY} goes through the client's own inventory key
     * path, not {@code setScreen} — the contract asks that opening the inventory be the
     * player's own key, and a screen installed behind it would be a second door to the same
     * window.
     */
    private void applyScreen(ScreenCommand command) {
        BridgeInputController controller = input;
        if (controller == null) {
            return;
        }
        ScreenInput value = command.value();
        boolean open =
                value.getControl()
                        == io.minekin.protocol.v1.ScreenControl.SCREEN_CONTROL_OPEN_INVENTORY;
        BridgeInputController.Outcome guard =
                controller.preflight(
                        monotonicNow(), command.deadlineNanos(), value.getGeneration(), open);
        if (!guard.applied()) {
            publishResult(
                    value.getActionId(),
                    value.getGeneration(),
                    ActionStatus.ACTION_STATUS_FAILED,
                    guard.refusalCode());
            LOGGER.warn("bridge refused screen {}: {}", value.getActionId(), guard.refusalCode());
            return;
        }
        WorldClientView view = worldView;
        if (view == null || !view.inWorld()) {
            publishResult(
                    value.getActionId(),
                    value.getGeneration(),
                    ActionStatus.ACTION_STATUS_FAILED,
                    WorldActions.REFUSED_NOT_IN_WORLD);
            LOGGER.warn(
                    "bridge refused screen {}: {}",
                    value.getActionId(),
                    WorldActions.REFUSED_NOT_IN_WORLD);
            return;
        }
        if (open) {
            view.openInventory();
        } else {
            view.closeScreen();
        }
        publishResult(
                value.getActionId(), value.getGeneration(), ActionStatus.ACTION_STATUS_ACCEPTED, "");
        LOGGER.info("bridge applied screen {} ({})", value.getActionId(), value.getControl());
    }

    /**
     * Clicks inside the screen the client already has open, and answers for it.
     *
     * <p>A GUI click is about the open container, so the guard does not require a free
     * keyboard — a screen holding it is the precondition, not a refusal. Then the sync id is
     * checked against the handler the client reports this instant ({@code GUI_SYNC_ID_MISMATCH}
     * if they differ, so a stale plan cannot click into a container the player opened
     * afterwards), and a recipe branch additionally refuses an id the version does not have
     * ({@code GUI_RECIPE_UNKNOWN}). A click that dispatches reports {@code STARTED}: the packet
     * left, and whether items actually moved is a fact the next observation's inventory delta
     * decides, never one the click itself may confirm.
     */
    private void applyGui(GuiClickCommand command) {
        BridgeInputController controller = input;
        if (controller == null) {
            return;
        }
        GuiClickInput value = command.value();
        BridgeInputController.Outcome guard =
                controller.preflight(
                        monotonicNow(), command.deadlineNanos(), value.getGeneration(), false);
        if (!guard.applied()) {
            publishResult(
                    value.getActionId(),
                    value.getGeneration(),
                    ActionStatus.ACTION_STATUS_FAILED,
                    guard.refusalCode());
            LOGGER.warn("bridge refused gui click {}: {}", value.getActionId(), guard.refusalCode());
            return;
        }
        WorldClientView view = worldView;
        if (view == null) {
            publishResult(
                    value.getActionId(),
                    value.getGeneration(),
                    ActionStatus.ACTION_STATUS_FAILED,
                    WorldActions.REFUSED_NOT_IN_WORLD);
            return;
        }
        Optional<String> refusal =
                WorldActions.guiSyncIdRefusal(
                        value.getSyncId(), view.screenOpen(), view.screenSyncId());
        if (refusal.isPresent()) {
            publishResult(
                    value.getActionId(),
                    value.getGeneration(),
                    ActionStatus.ACTION_STATUS_FAILED,
                    refusal.get());
            LOGGER.warn("bridge refused gui click {}: {}", value.getActionId(), refusal.get());
            return;
        }
        switch (value.getClickCase()) {
            case SLOT -> {
                GuiSlotClick slot = value.getSlot();
                view.clickSlot(slot.getSlotId(), slot.getButton(), slot.getMode());
                publishResult(
                        value.getActionId(),
                        value.getGeneration(),
                        ActionStatus.ACTION_STATUS_STARTED,
                        "");
                LOGGER.info("bridge clicked slot {} in {}", slot.getSlotId(), value.getActionId());
            }
            case RECIPE -> {
                GuiRecipeClick recipe = value.getRecipe();
                if (!view.recipeKnown(recipe.getRecipeId())) {
                    publishResult(
                            value.getActionId(),
                            value.getGeneration(),
                            ActionStatus.ACTION_STATUS_FAILED,
                            WorldActions.REFUSED_GUI_RECIPE_UNKNOWN);
                    LOGGER.warn(
                            "bridge refused gui click {}: {}",
                            value.getActionId(),
                            WorldActions.REFUSED_GUI_RECIPE_UNKNOWN);
                    return;
                }
                view.clickRecipe(recipe.getRecipeId(), recipe.getCraftAll());
                publishResult(
                        value.getActionId(),
                        value.getGeneration(),
                        ActionStatus.ACTION_STATUS_STARTED,
                        "");
                LOGGER.info(
                        "bridge clicked recipe {} in {}", recipe.getRecipeId(), value.getActionId());
            }
            default -> {
                // Reachable only if a command with no click slipped past the inbound shape
                // check; refused by name rather than silently applied to nothing.
                publishResult(
                        value.getActionId(),
                        value.getGeneration(),
                        ActionStatus.ACTION_STATUS_FAILED,
                        WorldActions.REFUSED_MALFORMED_CLICK);
                LOGGER.warn(
                        "bridge refused gui click {}: {}",
                        value.getActionId(),
                        WorldActions.REFUSED_MALFORMED_CLICK);
            }
        }
    }

    /** Publishes one action's answer, so every apply* method ends with a reply Core reads. */
    private void publishResult(
            String actionId, long generation, ActionStatus status, String reasonCode) {
        publishActionResult(
                ActionResult.newBuilder()
                        .setActionId(actionId)
                        .setGeneration(generation)
                        .setStatus(status)
                        .setReasonCode(reasonCode == null ? "" : reasonCode)
                        .build());
    }

    /** Client-thread shutdown/error hook; logs only after the bindings changed. */
    public void releaseInputsOnClientThread(
            BridgeInputController.ReleaseReason reason, String reasonCode) {
        releaseInputs(reason, reasonCode);
    }

    public long rejectedMessageCount() {
        return clientInbox.rejectedCount() + eventOutbox.rejectedCount();
    }

    /**
     * One must-deliver event, with the message type the event channel carries it
     * under.
     *
     * <p>The channel's sequence is shared across event types — the host requires
     * a contiguous one — so one writer owns both kinds and the type travels with
     * the payload rather than being decided by whoever reads the queue.
     */
    public record EventMessage(String messageType, com.google.protobuf.MessageLite payload) {
        public EventMessage {
            java.util.Objects.requireNonNull(messageType, "messageType");
            java.util.Objects.requireNonNull(payload, "payload");
        }
    }

    /**
     * Non-blocking client-thread handoff for the host lifecycle, on the same outbox
     * as everything else the Bridge must deliver.
     *
     * <p>Validity is checked here rather than at the call site because the invariants
     * are the ones that make the event readable: a phase the wire does not define,
     * a generation nobody is in, and a port that is present on a failure or absent on
     * a publication are each a message Core would have to guess about.
     */
    public boolean publishHostLifecycle(HostLifecycle lifecycle) {
        java.util.Objects.requireNonNull(lifecycle, "lifecycle");
        boolean opened = lifecycle.getPhase() == HostPhase.HOST_PHASE_LAN_OPENED;
        boolean named = lifecycle.getBoundPort() > 0 && lifecycle.getBoundPort() <= 65535;
        if (stopping.get()
                || !started.get()
                || event == null
                || lifecycle.getRequestId().isBlank()
                || lifecycle.getGeneration() == 0
                || lifecycle.getPhase() == HostPhase.HOST_PHASE_UNSPECIFIED
                || lifecycle.getPhase() == HostPhase.UNRECOGNIZED
                || opened != named) {
            LOGGER.warn("bridge dropped a host lifecycle report: {}", lifecycle.getPhase());
            return false;
        }
        if (!eventOutbox.offer(new EventMessage(HOST_LIFECYCLE_TYPE, lifecycle))) {
            LOGGER.error(
                    "bridge event outbox is full ({} held), failing closed on {}",
                    eventOutbox.size(),
                    lifecycle.getPhase());
            failClosed();
            return false;
        }
        return true;
    }

    /** Non-blocking client-thread handoff for must-deliver lifecycle events. */
    public boolean publishLifecycle(ConnectionLifecycle lifecycle) {
        java.util.Objects.requireNonNull(lifecycle, "lifecycle");
        if (stopping.get() || !started.get() || event == null || !validLifecycle(lifecycle)) {
            LOGGER.warn(
                    "bridge dropped a lifecycle report: stopping={} started={} event={} valid={}",
                    stopping.get(),
                    started.get(),
                    event != null,
                    validLifecycle(lifecycle));
            return false;
        }
        if (!eventOutbox.offer(new EventMessage(CONNECTION_LIFECYCLE_TYPE, lifecycle))) {
            // Worth saying out loud: this is the Bridge failing itself closed
            // because a phase it must deliver had nowhere to go, and the client
            // it is attached to will be cancelled a moment later. Without this
            // line the client simply stops, with no cause anywhere.
            LOGGER.error(
                    "bridge event outbox is full ({} held), failing closed on {}",
                    eventOutbox.size(),
                    lifecycle.getPhase());
            failClosed();
            return false;
        }
        return true;
    }

    /**
     * The first snapshot, for the same reason a phase is must-deliver: it is what
     * makes an attempt playable, and dropping it silently would leave a session
     * joined and going nowhere with nothing recorded about why.
     */
    public boolean publishObservation(InitialObservation observation) {
        java.util.Objects.requireNonNull(observation, "observation");
        if (stopping.get() || !started.get() || event == null) {
            return false;
        }
        if (!eventOutbox.offer(new EventMessage(INITIAL_OBSERVATION_TYPE, observation))) {
            LOGGER.error(
                    "bridge event outbox is full ({} held); dropping the first snapshot",
                    eventOutbox.size());
            failClosed();
            return false;
        }
        return true;
    }

    /**
     * The answer to one input command, which is must-deliver for the same reason
     * a phase is: a command with no answer is indistinguishable from one still
     * being carried out, and the difference matters most exactly when the answer
     * is a refusal.
     */
    public boolean publishActionResult(ActionResult result) {
        java.util.Objects.requireNonNull(result, "result");
        if (stopping.get() || !started.get() || event == null) {
            return false;
        }
        if (!eventOutbox.offer(new EventMessage(ACTION_RESULT_TYPE, result))) {
            LOGGER.error(
                    "bridge event outbox is full ({} held); dropping the result for {}",
                    eventOutbox.size(),
                    result.getActionId());
            failClosed();
            return false;
        }
        return true;
    }

    /**
     * The Bridge's own callback budget over one window — the one report it may drop.
     *
     * <p>Every other publisher here fails closed when the outbox is full, and each
     * time the reason is the same in kind: a lifecycle phase, a first snapshot and an
     * action result are things the session cannot proceed correctly without. A budget
     * window is the opposite case. It is a measurement of the Bridge, and stopping a
     * client because a measurement of the Bridge could not be delivered would make
     * the sampler the cause of the fault it exists to detect.
     *
     * <p>So a window the outbox had no room for is dropped and logged, and a reader
     * still sees that it happened: `window` is assigned when the window closes rather
     * than when it is published, so the delivered windows carry a hole exactly where
     * the dropped one was. That is a fact in the evidence rather than a counter that
     * would have to survive the same full outbox it is reporting on.
     */
    public boolean publishBudgetWindow(CallbackBudgetWindow window) {
        java.util.Objects.requireNonNull(window, "window");
        if (stopping.get() || !started.get() || event == null) {
            return false;
        }
        if (!eventOutbox.offer(new EventMessage(BUDGET_WINDOW_TYPE, window))) {
            LOGGER.warn(
                    "bridge dropped the {} budget window {}: the event outbox is full ({} held)",
                    window.getLabel(),
                    window.getWindow(),
                    eventOutbox.size());
            return false;
        }
        return true;
    }

    /**
     * The recurring player-equivalent view, published best-effort.
     *
     * <p>Unlike a lifecycle phase, a first snapshot or an action result, an observation the
     * outbox had no room for is dropped rather than failing the client closed. It is a fresh
     * read of the same state the next tick reads again; stopping a running client because one
     * snapshot of it could not be delivered would make the view a cause of the fault it exists
     * to reveal. The dropped frames simply make the delivered ticks non-contiguous, which a
     * reader can see.
     */
    public boolean publishWorldObservation(WorldObservation observation) {
        java.util.Objects.requireNonNull(observation, "observation");
        if (stopping.get() || !started.get() || event == null) {
            return false;
        }
        if (!eventOutbox.offer(new EventMessage(WORLD_OBSERVATION_TYPE, observation))) {
            LOGGER.warn(
                    "bridge dropped a world observation for generation {}: the event outbox"
                            + " is full ({} held)",
                    observation.getGeneration(),
                    eventOutbox.size());
            return false;
        }
        return true;
    }

    /**
     * Answers an inbound action whose capability Core never negotiated, by name.
     *
     * <p>Refused rather than dropped or failed-closed: §1 makes honoring a command the
     * negotiation never covered the dangerous direction of the mistake, and the safe one is
     * a named {@code CAPABILITY_NOT_GRANTED} in the reply — visible to Core as its own bug
     * rather than silent, and never a reason to stop a client that is otherwise running.
     */
    private void publishCapabilityRefusal(String actionId, long generation) {
        publishResult(
                actionId,
                generation,
                ActionStatus.ACTION_STATUS_FAILED,
                WorldActions.REFUSED_CAPABILITY_NOT_GRANTED);
    }

    @Override
    public void close() {
        if (!stopping.compareAndSet(false, true)) {
            return;
        }
        // Closing invalidates every queued command. The client-thread caller may
        // already have released input, but SAFE_STOP must still be the only next
        // message if a tick drains again during shutdown.
        clientInbox.replaceWith(Notice.SAFE_STOP);
        closeQuietly(control);
        closeQuietly(event);
        Thread worker = thread;
        if (worker != null) {
            worker.interrupt();
        }
        Thread writer = eventThread;
        if (writer != null) {
            writer.interrupt();
        }
    }

    private void run() {
        try {
            BridgeBootstrapDescriptor raw = DescriptorLoader.loadAndDelete(descriptorPath);
            BootstrapDescriptorAdapter.AdaptedDescriptor descriptor =
                    BootstrapDescriptorAdapter.adapt(raw, identity);
            phases.transition(BridgePhaseMachine.Phase.IPC_CONNECTING);
            control = connect(
                    descriptor.endpoints().control(), Channel.CHANNEL_CONTROL, descriptor.maxFrameBytes());
            event = connect(
                    descriptor.endpoints().event(), Channel.CHANNEL_EVENT, descriptor.maxFrameBytes());
            HeartbeatState heartbeat = handshake(descriptor);
            startEventWriter(descriptor);
            heartbeatLoop(descriptor, heartbeat);
        } catch (Exception error) {
            if (!stopping.get()) {
                failClosed(reasonFor(error));
            }
        } finally {
            closeQuietly(control);
            closeQuietly(event);
        }
    }

    private NioEnvelopeChannel connect(
            io.minekin.protocol.v1.IpcEndpoint endpoint, Channel channel, int maxFrameBytes)
            throws IOException {
        SocketChannel socket = EndpointConnector.connect(endpoint, connectTimeout);
        try {
            return new NioEnvelopeChannel(socket, channel, maxFrameBytes);
        } catch (IOException | RuntimeException error) {
            socket.close();
            throw error;
        }
    }

    private HeartbeatState handshake(BootstrapDescriptorAdapter.AdaptedDescriptor descriptor)
            throws IOException {
        HandshakeGate handshake = new HandshakeGate(descriptor.expected(), phases);
        Envelope bridgeHello = envelope(
                descriptor,
                BRIDGE_HELLO_TYPE,
                Channel.CHANNEL_CONTROL,
                1,
                BootstrapDescriptorAdapter.toProto(handshake.bridgeHello()).toByteString());
        control.write(bridgeHello, handshakeTimeout);

        EnvelopeGate gate = new EnvelopeGate(
                new EnvelopeGate.Expected(
                        descriptor.expected().protocolMajor(),
                        descriptor.expected().protocolMinor(),
                        descriptor.expected().kinId(),
                        descriptor.expected().sessionId(),
                        descriptor.expected().generation(),
                        descriptor.expected().clientInstanceId()),
                Channel.CHANNEL_CONTROL,
                Set.of(
                        CORE_HELLO_TYPE,
                        HEARTBEAT_TYPE,
                        CONNECT_WORLD_TYPE,
                        CANCEL_CONNECTION_TYPE,
                        OPEN_LAN_TYPE,
                        RELEASE_ALL_INPUTS_TYPE,
                        MOVE_INPUT_TYPE,
                        LOOK_INPUT_TYPE,
                        USE_INPUT_TYPE,
                        AIM_INPUT_TYPE,
                        MINE_INPUT_TYPE,
                        HOTBAR_SELECT_INPUT_TYPE,
                        SCREEN_INPUT_TYPE,
                        GUI_CLICK_INPUT_TYPE));
        Envelope reply = control.read(handshakeTimeout);
        gate.validate(reply);
        if (!CORE_HELLO_TYPE.equals(reply.getMessageType())) {
            throw new IOException("first control message is not CoreHello");
        }
        CoreHello coreHello = CoreHello.parseFrom(reply.getPayload());
        HandshakeGate.CoreHelloData accepted = BootstrapDescriptorAdapter.fromProto(coreHello);
        if (!handshake.accept(accepted)) {
            throw new IOException("CoreHello proof or negotiated values were rejected");
        }
        if (!clientInbox.offer(Notice.OBSERVE_ONLY)) {
            throw new IOException("client notice queue is full after handshake");
        }
        BridgeInputController created = new BridgeInputController(
                keySink,
                viewSink,
                new InputWatchdog(
                        Duration.ofMillis(coreHello.getHeartbeatIntervalMs()).toNanos(),
                        INPUT_MISSED_HEARTBEATS),
                descriptor.expected().generation());
        created.observeCoreMessage(monotonicNow());
        input = created;
        // Kept for the whole session: the heartbeat loop refuses an action whose capability is
        // not here, and the client tick asks whether the recurring observation is granted
        // before it reads the world. The generation is the descriptor's — the one value both
        // this Bridge and Core agreed the session is numbered with.
        negotiatedCapabilities = Set.copyOf(accepted.acceptedCapabilities());
        sessionGeneration = descriptor.expected().generation();
        return new HeartbeatState(
                gate,
                Duration.ofMillis(
                        Math.multiplyExact(
                                coreHello.getHeartbeatIntervalMs(),
                                (long) CORE_ABSENT_INTERVALS)),
                accepted.acceptedCapabilities());
    }

    private void startEventWriter(BootstrapDescriptorAdapter.AdaptedDescriptor descriptor) {
        Thread writer = new Thread(() -> eventWriterLoop(descriptor), "minekin-bridge-events");
        writer.setDaemon(true);
        eventThread = writer;
        writer.start();
    }

    private void eventWriterLoop(BootstrapDescriptorAdapter.AdaptedDescriptor descriptor) {
        long sequence = 1;
        try {
            while (!stopping.get()) {
                EventMessage message = eventOutbox.take();
                Envelope outbound = envelope(
                        descriptor,
                        message.messageType(),
                        Channel.CHANNEL_EVENT,
                        sequence,
                        message.payload().toByteString());
                try {
                    event.write(outbound, handshakeTimeout);
                } catch (IOException error) {
                    throw new IpcLost(error);
                }
                if (sequence == Long.MAX_VALUE) {
                    throw new IOException("event sequence exhausted the P0 signed range");
                }
                sequence++;
            }
        } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            if (!stopping.get()) {
                failClosed();
            }
        } catch (Exception error) {
            if (!stopping.get()) {
                failClosed();
            }
        }
    }

    private void heartbeatLoop(
            BootstrapDescriptorAdapter.AdaptedDescriptor descriptor, HeartbeatState state)
            throws IOException {
        long heartbeatDeadline = heartbeatDeadline(state.timeout());
        while (!stopping.get()) {
            long remaining = heartbeatDeadline - System.nanoTime();
            if (remaining <= 0) {
                throw new SocketTimeoutException("Bridge heartbeat timed out");
            }
            Envelope envelope;
            try {
                envelope = control.read(Duration.ofNanos(remaining));
            } catch (IOException error) {
                // Not a protocol violation: the socket itself is done. Which of the
                // two it is decides what the release is called, and a Core that died
                // must not be reported as a Bridge that broke.
                throw new IpcLost(error);
            }
            state.gate().validate(envelope);
            if (HEARTBEAT_TYPE.equals(envelope.getMessageType())) {
                Heartbeat heartbeat = Heartbeat.parseFrom(envelope.getPayload());
                if (heartbeat.getGeneration() != descriptor.expected().generation()
                        || heartbeat.getMonotonicNs() == 0) {
                    throw new IOException("heartbeat identity is invalid");
                }
                observeCoreMessage();
                heartbeatDeadline = heartbeatDeadline(state.timeout());
            } else if (CONNECT_WORLD_TYPE.equals(envelope.getMessageType())) {
                ConnectWorld command = ConnectWorld.parseFrom(envelope.getPayload());
                validateConnectDeadline(command, envelope.getMonotonicNs());
                admissionCommands.acceptConnect(command, state.capabilities());
                observeCoreMessage();
                if (!clientInbox.offer(new ConnectCommand(command))) {
                    throw new IOException("client inbox is full for ConnectWorld");
                }
            } else if (RELEASE_ALL_INPUTS_TYPE.equals(envelope.getMessageType())) {
                ReleaseAllInputs command = ReleaseAllInputs.parseFrom(envelope.getPayload());
                validateRelease(command);
                observeCoreMessage();
                // Release is deliberately fail-safe: a stale positive generation
                // still lifts keys. It may not grant control, so suppressing it on a
                // generation mismatch would only preserve unsafe state.
                if (!clientInbox.offer(new ReleaseCommand(command))) {
                    throw new IOException("client inbox is full for ReleaseAllInputs");
                }
            } else if (MOVE_INPUT_TYPE.equals(envelope.getMessageType())) {
                MoveInput command = onLocalClock(
                        MoveInput.parseFrom(envelope.getPayload()), envelope.getMonotonicNs());
                validateMove(command);
                if (!state.capabilities().contains(HandshakeGate.MOVE_CAPABILITY)) {
                    // A command the negotiation never covered. Refused here rather
                    // than dropped: a Core that believes it can move a client it
                    // never agreed to move has a bug, and this is where it shows.
                    throw new IOException("MoveInput arrived without the movement capability");
                }
                observeCoreMessage();
                if (!clientInbox.offer(new MoveCommand(command))) {
                    throw new IOException("client inbox is full for MoveInput");
                }
            } else if (LOOK_INPUT_TYPE.equals(envelope.getMessageType())) {
                LookInput command = onLocalClock(
                        LookInput.parseFrom(envelope.getPayload()), envelope.getMonotonicNs());
                validateLook(command);
                if (!state.capabilities().contains(HandshakeGate.LOOK_CAPABILITY)) {
                    throw new IOException("LookInput arrived without the look capability");
                }
                observeCoreMessage();
                if (!clientInbox.offer(new LookCommand(command))) {
                    throw new IOException("client inbox is full for LookInput");
                }
            } else if (USE_INPUT_TYPE.equals(envelope.getMessageType())) {
                UseInput command = onLocalClock(
                        UseInput.parseFrom(envelope.getPayload()), envelope.getMonotonicNs());
                validateUse(command);
                if (!state.capabilities().contains(HandshakeGate.USE_CAPABILITY)) {
                    throw new IOException("UseInput arrived without the use capability");
                }
                observeCoreMessage();
                if (!clientInbox.offer(new UseCommand(command))) {
                    throw new IOException("client inbox is full for UseInput");
                }
            } else if (AIM_INPUT_TYPE.equals(envelope.getMessageType())) {
                AimInput command = AimInput.parseFrom(envelope.getPayload());
                validateAim(command);
                handleActionOrRefuseCapability(
                        state,
                        HandshakeGate.AIM_CAPABILITY,
                        command.getActionId(),
                        command.getGeneration(),
                        command.getDeadlineMonotonicNs(),
                        envelope.getMonotonicNs(),
                        deadline -> new AimCommand(command, deadline),
                        "AimInput");
            } else if (MINE_INPUT_TYPE.equals(envelope.getMessageType())) {
                MineInput command = MineInput.parseFrom(envelope.getPayload());
                validateMine(command);
                handleActionOrRefuseCapability(
                        state,
                        HandshakeGate.MINE_CAPABILITY,
                        command.getActionId(),
                        command.getGeneration(),
                        command.getDeadlineMonotonicNs(),
                        envelope.getMonotonicNs(),
                        deadline -> new MineCommand(command, deadline),
                        "MineInput");
            } else if (HOTBAR_SELECT_INPUT_TYPE.equals(envelope.getMessageType())) {
                HotbarSelectInput command = HotbarSelectInput.parseFrom(envelope.getPayload());
                validateHotbar(command);
                handleActionOrRefuseCapability(
                        state,
                        HandshakeGate.HOTBAR_CAPABILITY,
                        command.getActionId(),
                        command.getGeneration(),
                        command.getDeadlineMonotonicNs(),
                        envelope.getMonotonicNs(),
                        deadline -> new HotbarSelectCommand(command, deadline),
                        "HotbarSelectInput");
            } else if (SCREEN_INPUT_TYPE.equals(envelope.getMessageType())) {
                ScreenInput command = ScreenInput.parseFrom(envelope.getPayload());
                validateScreen(command);
                handleActionOrRefuseCapability(
                        state,
                        HandshakeGate.SCREEN_CAPABILITY,
                        command.getActionId(),
                        command.getGeneration(),
                        command.getDeadlineMonotonicNs(),
                        envelope.getMonotonicNs(),
                        deadline -> new ScreenCommand(command, deadline),
                        "ScreenInput");
            } else if (GUI_CLICK_INPUT_TYPE.equals(envelope.getMessageType())) {
                GuiClickInput command = GuiClickInput.parseFrom(envelope.getPayload());
                validateGui(command);
                handleActionOrRefuseCapability(
                        state,
                        HandshakeGate.GUI_CAPABILITY,
                        command.getActionId(),
                        command.getGeneration(),
                        command.getDeadlineMonotonicNs(),
                        envelope.getMonotonicNs(),
                        deadline -> new GuiClickCommand(command, deadline),
                        "GuiClickInput");
            } else if (OPEN_LAN_TYPE.equals(envelope.getMessageType())) {
                OpenLan command = OpenLan.parseFrom(envelope.getPayload());
                validateOpenLanDeadline(command, envelope.getMonotonicNs());
                if (!state.capabilities().contains(HandshakeGate.HOST_LAN_CAPABILITY)) {
                    // Refused rather than dropped, for the same reason an input
                    // without its capability is: a Core that believes it can publish
                    // a world it never negotiated for has a bug, and this is where
                    // the bug becomes visible instead of silent.
                    throw new IOException("OpenLan arrived without the host capability");
                }
                observeCoreMessage();
                if (!clientInbox.offer(new OpenLanCommand(command))) {
                    throw new IOException("client inbox is full for OpenLan");
                }
            } else if (CANCEL_CONNECTION_TYPE.equals(envelope.getMessageType())) {
                CancelConnection command = CancelConnection.parseFrom(envelope.getPayload());
                admissionCommands.acceptCancel(command, state.capabilities());
                observeCoreMessage();
                if (!clientInbox.offer(new CancelCommand(command))) {
                    throw new IOException("client inbox is full for CancelConnection");
                }
            } else {
                throw new IOException("CoreHello may not be replayed after activation");
            }
        }
    }

    private static Envelope envelope(
            BootstrapDescriptorAdapter.AdaptedDescriptor descriptor,
            String messageType,
            Channel channel,
            long sequence,
            ByteString payload) {
        HandshakeGate.Expected expected = descriptor.expected();
        return Envelope.newBuilder()
                .setProtocol(ProtocolVersion.newBuilder()
                        .setMajor(expected.protocolMajor())
                        .setMinor(expected.protocolMinor()))
                .setMessageType(messageType)
                .setChannel(channel)
                .setSequence(sequence)
                .setKinId(expected.kinId())
                .setSessionId(expected.sessionId())
                .setGeneration(expected.generation())
                .setClientInstanceId(expected.clientInstanceId())
                .setMonotonicNs(monotonicNow())
                .setPayload(payload)
                .build();
    }

    private static boolean validLifecycle(ConnectionLifecycle lifecycle) {
        if (lifecycle.getGeneration() == 0
                || lifecycle.getServerProfileId().isBlank()
                || !lifecycle.getServerProfileRevision().matches("[0-9a-f]{64}")
                || lifecycle.getPhase() == ConnectionPhase.CONNECTION_PHASE_UNSPECIFIED
                || lifecycle.getPhase() == ConnectionPhase.UNRECOGNIZED
                || lifecycle.getFailureReason() == AdmissionFailureReason.UNRECOGNIZED
                // Same rule as the reason: a policy this build cannot name is not a
                // value to send and let Core guess about. UNSPECIFIED means "this
                // report says nothing about a policy", which is its own legitimate
                // message, so only UNRECOGNIZED is refused here.
                || lifecycle.getAppliedResourcePackPolicy() == ResourcePackPolicy.UNRECOGNIZED) {
            return false;
        }
        boolean terminalPhase = switch (lifecycle.getPhase()) {
            case CONNECTION_PHASE_DISCONNECTED,
                    CONNECTION_PHASE_FAILED,
                    CONNECTION_PHASE_CANCELLED -> true;
            default -> false;
        };
        if (terminalPhase != lifecycle.getTerminal()) {
            return false;
        }
        // Core classifies on the phase and the reason together, so a reason that
        // does not belong to the phase is a contradiction, not extra detail.
        AdmissionFailureReason reason = lifecycle.getFailureReason();
        return switch (lifecycle.getPhase()) {
            case CONNECTION_PHASE_FAILED ->
                    reason != AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNSPECIFIED
                            && reason != AdmissionFailureReason.ADMISSION_FAILURE_REASON_CANCELLED;
            case CONNECTION_PHASE_CANCELLED ->
                    reason == AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNSPECIFIED
                            || reason
                                    == AdmissionFailureReason.ADMISSION_FAILURE_REASON_CANCELLED;
            default -> reason == AdmissionFailureReason.ADMISSION_FAILURE_REASON_UNSPECIFIED;
        };
    }

    /**
     * Hands the input back on the client thread. Faults arrive here through the
     * terminal inbox notice; normal shutdown calls the explicit client-thread hook.
     */
    private void releaseInputs(BridgeInputController.ReleaseReason reason, String reasonCode) {
        BridgeInputController controller = input;
        if (controller == null) {
            return;
        }
        java.util.List<String> released = controller.releaseAll(reason);
        if (reasonCode == null || reasonCode.isBlank()) {
            LOGGER.info("bridge released {} input(s) after {}", released.size(), reason);
        } else {
            LOGGER.info(
                    "bridge released {} input(s) after {} ({})",
                    released.size(),
                    reason,
                    reasonCode);
        }
    }

    private void observeCoreMessage() {
        BridgeInputController controller = input;
        if (controller != null) {
            controller.observeCoreMessage(monotonicNow());
        }
    }

    static void validateRelease(ReleaseAllInputs command) throws IOException {
        if (command.getActionId().isBlank()
                || command.getActionId().length() > 128
                || command.getGeneration() == 0
                || !command.getReasonCode().matches("[A-Z0-9_]{1,64}")) {
            throw new IOException("ReleaseAllInputs identity or reason is invalid");
        }
    }

    /**
     * Refuses a connect command that Core has already stopped waiting for.
     *
     * <p>The deadline and the envelope's own timestamp come from the same
     * clock — Core's — so their difference is a duration, and a duration is the
     * only thing two processes without a shared origin can agree on. Comparing
     * the raw deadline against this JVM's {@code System.nanoTime()} would be
     * comparing two unrelated numbers and would pass or fail by accident.
     *
     * <p>This is checked when the command is read rather than when the client
     * tick consumes it, because that is the moment the sender's stamp is still
     * on hand. Starting a connection Core has given up on is the failure this
     * exists to prevent: it would put a client in a world nobody is waiting
     * for, under a generation Core no longer tracks.
     */
    static void validateOpenLanDeadline(OpenLan command, long receivedAtNanos) throws IOException {
        long remaining;
        try {
            remaining = Math.subtractExact(command.getDeadlineMonotonicNs(), receivedAtNanos);
        } catch (ArithmeticException overflow) {
            throw new IOException("OpenLan deadline is not a usable duration");
        }
        if (remaining <= 0) {
            throw new IOException("OpenLan expired before the client could act on it");
        }
    }

    static void validateConnectDeadline(ConnectWorld command, long receivedAtNanos) throws IOException {
        long remaining;
        try {
            remaining = Math.subtractExact(command.getDeadlineMonotonicNs(), receivedAtNanos);
        } catch (ArithmeticException overflow) {
            throw new IOException("ConnectWorld deadline is not a usable duration");
        }
        if (remaining <= 0) {
            throw new IOException("ConnectWorld expired before the client could act on it");
        }
    }

    /**
     * Restates a movement command's deadline in this JVM's clock, or in the past.
     *
     * <p>The deadline and the envelope's own timestamp come from the same clock —
     * Core's — so their difference is a duration, and a duration is the only thing
     * two processes without a shared origin can agree on. Comparing Core's raw
     * deadline against {@code System.nanoTime()} would be comparing two unrelated
     * numbers and would pass or fail by accident; the same reasoning already
     * governs the connect deadline.
     *
     * <p>A command whose deadline has already passed is not an error: it is a
     * command Core stopped waiting for, and the controller refuses exactly that
     * with a code in the result Core reads. So the deadline is moved into the past
     * rather than thrown on, unlike a connect — starting a connection nobody waits
     * for is unsafe, while not pressing a key is the safe answer to a late
     * command.
     */
    static MoveInput onLocalClock(MoveInput command, long receivedAtNanos) {
        if (command.getDeadlineMonotonicNs() == 0) {
            return command.toBuilder().setDeadlineMonotonicNs(0).build();
        }
        long remaining;
        try {
            remaining = Math.subtractExact(command.getDeadlineMonotonicNs(), receivedAtNanos);
        } catch (ArithmeticException overflow) {
            remaining = 0;
        }
        if (remaining <= 0) {
            return command.toBuilder().setDeadlineMonotonicNs(monotonicNow() - 1).build();
        }
        return command.toBuilder()
                .setDeadlineMonotonicNs(Math.addExact(monotonicNow(), remaining))
                .build();
    }

    /**
     * The same restatement for a look, which carries the same kind of deadline.
     */
    static LookInput onLocalClock(LookInput command, long receivedAtNanos) {
        if (command.getDeadlineMonotonicNs() == 0) {
            return command.toBuilder().setDeadlineMonotonicNs(0).build();
        }
        long remaining;
        try {
            remaining = Math.subtractExact(command.getDeadlineMonotonicNs(), receivedAtNanos);
        } catch (ArithmeticException overflow) {
            remaining = 0;
        }
        if (remaining <= 0) {
            return command.toBuilder().setDeadlineMonotonicNs(monotonicNow() - 1).build();
        }
        return command.toBuilder()
                .setDeadlineMonotonicNs(Math.addExact(monotonicNow(), remaining))
                .build();
    }

    /**
     * The same restatement for a use, which carries the same kind of deadline.
     *
     * <p>The third of these is a copy of the other two rather than one method
     * over all of them: protobuf's builders have no common supertype to write
     * that over, so the choice is three short methods or reflection, and this
     * file already chose.
     */
    static UseInput onLocalClock(UseInput command, long receivedAtNanos) {
        if (command.getDeadlineMonotonicNs() == 0) {
            return command.toBuilder().setDeadlineMonotonicNs(0).build();
        }
        long remaining;
        try {
            remaining = Math.subtractExact(command.getDeadlineMonotonicNs(), receivedAtNanos);
        } catch (ArithmeticException overflow) {
            remaining = 0;
        }
        if (remaining <= 0) {
            return command.toBuilder().setDeadlineMonotonicNs(monotonicNow() - 1).build();
        }
        return command.toBuilder()
                .setDeadlineMonotonicNs(Math.addExact(monotonicNow(), remaining))
                .build();
    }

    /**
     * Refuses a look that is not one, for the reasons a movement command is.
     */
    static void validateUse(UseInput command) {
        if (command.getActionId().isBlank()
                || command.getActionId().length() > 128
                || command.getGeneration() == 0
                || command.getLeaseId().isBlank()
                || command.getLeaseId().length() > 128) {
            throw new IllegalArgumentException("UseInput violates the negotiated input bounds");
        }
    }

    static void validateLook(LookInput command) {
        if (command.getActionId().isBlank()
                || command.getActionId().length() > 128
                || command.getGeneration() == 0
                || command.getLeaseId().isBlank()
                || command.getLeaseId().length() > 128
                || !Float.isFinite(command.getDeltaYawDegrees())
                || !Float.isFinite(command.getDeltaPitchDegrees())) {
            throw new IllegalArgumentException("LookInput violates the negotiated input bounds");
        }
    }

    /**
     * Refuses a movement command that is not one, before it reaches the client.
     *
     * <p>This is about identity and shape, not about whether the command is still
     * wanted: a stale generation or a passed deadline is a refusal the controller
     * reports with a code, because a Core that is merely late is not a Core that is
     * broken. A blank action, a generation nobody could be, a missing lease, or an
     * axis that is not a number is a command that cannot be answered for at all.
     */
    static void validateMove(MoveInput command) {
        if (command.getActionId().isBlank()
                || command.getActionId().length() > 128
                || command.getGeneration() == 0
                || command.getLeaseId().isBlank()
                || command.getLeaseId().length() > 128
                || !axis(command.getForward())
                || !axis(command.getStrafe())) {
            throw new IllegalArgumentException("MoveInput violates the negotiated input bounds");
        }
    }

    private static boolean axis(float value) {
        return Float.isFinite(value) && value >= -1.0f && value <= 1.0f;
    }

    /**
     * The identity every inbound action shares: an action to answer for, a generation that
     * could exist, and a lease that names one. A blank or over-long id, or a generation of
     * zero, is a command that cannot be answered at all — not a stale one — so it is a shape
     * fault (fail-closed), exactly like a movement command's, rather than a named refusal.
     */
    private static boolean identityOk(String actionId, String leaseId, long generation) {
        return !actionId.isBlank()
                && actionId.length() <= 128
                && generation != 0
                && !leaseId.isBlank()
                && leaseId.length() <= 128;
    }

    /**
     * A turn that is not a turn is refused before it reaches the client, on the same identity
     * bounds as a movement command plus the finite-angle rule a look uses: an angle that is
     * not a number is not an aim that would move a little, it is a command with no heading.
     */
    static void validateAim(AimInput command) {
        if (!identityOk(command.getActionId(), command.getLeaseId(), command.getGeneration())
                || !Float.isFinite(command.getYawDegrees())
                || !Float.isFinite(command.getPitchDegrees())) {
            throw new IllegalArgumentException("AimInput violates the negotiated input bounds");
        }
    }

    /** The attack key held or let go; the target match is a semantic check made on the tick. */
    static void validateMine(MineInput command) {
        if (!identityOk(command.getActionId(), command.getLeaseId(), command.getGeneration())) {
            throw new IllegalArgumentException("MineInput violates the negotiated input bounds");
        }
    }

    /** Slot range is a named refusal ({@code HOTBAR_SLOT_OUT_OF_RANGE}), not a shape fault. */
    static void validateHotbar(HotbarSelectInput command) {
        if (!identityOk(
                command.getActionId(), command.getLeaseId(), command.getGeneration())) {
            throw new IllegalArgumentException(
                    "HotbarSelectInput violates the negotiated input bounds");
        }
    }

    /** A screen control that names no action this build can take is a command with no meaning. */
    static void validateScreen(ScreenInput command) {
        io.minekin.protocol.v1.ScreenControl control = command.getControl();
        if (!identityOk(command.getActionId(), command.getLeaseId(), command.getGeneration())
                || control == io.minekin.protocol.v1.ScreenControl.UNRECOGNIZED
                || control == io.minekin.protocol.v1.ScreenControl.SCREEN_CONTROL_UNSPECIFIED) {
            throw new IllegalArgumentException(
                    "ScreenInput violates the negotiated input bounds");
        }
    }

    /**
     * A GUI click must name a click: oneof empty, a slot mode the build cannot map, or a
     * recipe id that is blank are each a command that cannot be answered, so they fail closed
     * like a malformed movement. The sync id and the recipe's existence are semantic checks
     * made on the tick, refused by name there, because a stale id is a real click against the
     * wrong window rather than a command with no window to speak of.
     */
    static void validateGui(GuiClickInput command) {
        if (!identityOk(command.getActionId(), command.getLeaseId(), command.getGeneration())
                || command.getClickCase() == GuiClickInput.ClickCase.CLICK_NOT_SET) {
            throw new IllegalArgumentException(
                    "GuiClickInput violates the negotiated input bounds");
        }
        switch (command.getClickCase()) {
            case SLOT -> {
                io.minekin.protocol.v1.SlotClickMode mode = command.getSlot().getMode();
                if (mode == io.minekin.protocol.v1.SlotClickMode.UNRECOGNIZED
                        || mode == io.minekin.protocol.v1.SlotClickMode.SLOT_CLICK_MODE_UNSPECIFIED) {
                    throw new IllegalArgumentException(
                            "GuiClickInput slot click names no supported mode");
                }
            }
            case RECIPE -> {
                if (command.getRecipe().getRecipeId().isBlank()) {
                    throw new IllegalArgumentException(
                            "GuiClickInput recipe click names no recipe");
                }
            }
            default -> throw new IllegalArgumentException(
                    "GuiClickInput names neither a slot nor a recipe");
        }
    }

    /**
     * Restates a command's deadline in this JVM's clock, the same way {@code onLocalClock}
     * restates a movement's.
     *
     * <p>The deadline and the envelope's stamp are both Core's clock, so only their difference
     * is a duration two processes can agree on; comparing the raw deadline against
     * {@code System.nanoTime()} would compare unrelated numbers and pass by accident. Unlike a
     * connect, a late input command is not an error: it is a command Core stopped waiting for,
     * and the controller refuses exactly that with a code, so an elapsed deadline is moved one
     * nanosecond into the past rather than thrown on.
     */
    static long restampDeadline(long coreDeadline, long receivedAtNanos) {
        if (coreDeadline == 0) {
            return 0;
        }
        long remaining;
        try {
            remaining = Math.subtractExact(coreDeadline, receivedAtNanos);
        } catch (ArithmeticException overflow) {
            remaining = 0;
        }
        if (remaining <= 0) {
            return monotonicNow() - 1;
        }
        return Math.addExact(monotonicNow(), remaining);
    }

    /**
     * The one path every S2 action takes after its shape is validated: refuse by name if its
     * capability was never negotiated, otherwise restate its deadline and hand it to the
     * client tick.
     *
     * <p>Deliberately not the movement path's rule. A movement or use command that arrives
     * without its capability throws and fails the Bridge closed, because honoring a steering
     * command nobody agreed to is unsafe to leave running; an S2 action is refused by name
     * instead, which answers Core's own bug back to it and stops nothing that is otherwise
     * healthy. The command reaches the client only when the capability is present, so a
     * refused command never reads a crosshair or taps a key.
     */
    private void handleActionOrRefuseCapability(
            HeartbeatState state,
            String capability,
            String actionId,
            long generation,
            long coreDeadline,
            long receivedAtNanos,
            java.util.function.LongFunction<ClientMessage> commandFactory,
            String label)
            throws IOException {
        if (!state.capabilities().contains(capability)) {
            publishCapabilityRefusal(actionId, generation);
            observeCoreMessage();
            LOGGER.warn(
                    "bridge refused {}: {} (capability {} was not negotiated)",
                    actionId,
                    WorldActions.REFUSED_CAPABILITY_NOT_GRANTED,
                    capability);
            return;
        }
        long deadline = restampDeadline(coreDeadline, receivedAtNanos);
        observeCoreMessage();
        if (!clientInbox.offer(commandFactory.apply(deadline))) {
            throw new IOException("client inbox is full for " + label);
        }
    }

    private void failClosed() {
        failClosed(BridgeInputController.ReleaseReason.BRIDGE_FAULT);
    }

    /**
     * Fails closed, remembering why, because the release that follows carries it.
     *
     * <p>The reason is the caller's and it has to be: a Core whose socket went away
     * and a Bridge that broke its own invariants are different facts about the run,
     * and a log that calls both `BRIDGE_FAULT` sends an operator to look at the
     * wrong process.
     */
    private void failClosed(BridgeInputController.ReleaseReason reason) {
        if (!stopping.compareAndSet(false, true)) {
            return;
        }
        faultReason = reason;
        LOGGER.error("bridge is failing closed ({}); the client will be stopped by its next tick", reason);
        phases.safeStop();
        clientInbox.replaceWith(Notice.SAFE_STOP);
        closeQuietly(control);
        closeQuietly(event);
        Thread controlWorker = thread;
        if (controlWorker != null && controlWorker != Thread.currentThread()) {
            controlWorker.interrupt();
        }
        Thread writer = eventThread;
        if (writer != null && writer != Thread.currentThread()) {
            writer.interrupt();
        }
    }

    /**
     * Whether a failure is the channel going away or the Bridge's own fault.
     *
     * <p>Only the transport is marked: a socket that closed, a peer that reset it,
     * or one that stopped answering are all the same fact about the run, and every
     * other way of failing closed is the Bridge refusing to go on.
     */
    static BridgeInputController.ReleaseReason reasonFor(Exception error) {
        boolean channelWentAway =
                error instanceof IpcLost || error instanceof SocketTimeoutException;
        return channelWentAway
                ? BridgeInputController.ReleaseReason.IPC_LOST
                : BridgeInputController.ReleaseReason.BRIDGE_FAULT;
    }

    /** The channel went away, as opposed to the Bridge or the contract breaking. */
    static final class IpcLost extends IOException {
        IpcLost(IOException cause) {
            super(cause.getMessage(), cause);
        }
    }

    private static Duration requirePositive(Duration value, String name) {
        if (value == null || value.isZero() || value.isNegative()) {
            throw new IllegalArgumentException(name + " must be positive");
        }
        return value;
    }

    private static long heartbeatDeadline(Duration timeout) {
        try {
            return Math.addExact(System.nanoTime(), timeout.toNanos());
        } catch (ArithmeticException error) {
            throw new IllegalArgumentException("heartbeat timeout is too large", error);
        }
    }

    /** Package-private so a test can measure a translated deadline against it. */
    static long monotonicNow() {
        return Math.max(1, System.nanoTime() - MONOTONIC_ORIGIN);
    }

    private static void closeQuietly(AutoCloseable closeable) {
        if (closeable != null) {
            try {
                closeable.close();
            } catch (Exception ignored) {
                // The session is already stopping or failed closed.
            }
        }
    }

    public sealed interface ClientMessage
            permits Notice,
                    ConnectCommand,
                    CancelCommand,
                    OpenLanCommand,
                    ReleaseCommand,
                    MoveCommand,
                    LookCommand,
                    UseCommand,
                    AimCommand,
                    MineCommand,
                    HotbarSelectCommand,
                    ScreenCommand,
                    GuiClickCommand {}

    public enum Notice implements ClientMessage {
        OBSERVE_ONLY,
        SAFE_STOP
    }

    public record ConnectCommand(ConnectWorld value) implements ClientMessage {}

    public record CancelCommand(CancelConnection value) implements ClientMessage {}

    /**
     * A command to publish the world this client is hosting.
     *
     * <p>Its own type rather than another field on an existing one: what it asks for
     * is a lifecycle change to the server in this process, which is the one thing the
     * boundary contract lets an adapter do and nothing else may.
     */
    public record OpenLanCommand(OpenLan value) implements ClientMessage {}

    public record ReleaseCommand(ReleaseAllInputs value) implements ClientMessage {}

    public record MoveCommand(MoveInput value) implements ClientMessage {}

    public record LookCommand(LookInput value) implements ClientMessage {}

    public record UseCommand(UseInput value) implements ClientMessage {}

    /**
     * An S2 action queued for the client tick, with its deadline already restated into this
     * JVM's clock.
     *
     * <p>The restamped deadline travels beside the message rather than being written back into
     * it because protobuf has no common supertype for the five builders, and a command that
     * could not carry its sender's stamp forward would be compared against an unrelated clock.
     * Each record is its own type so the client-thread router answers each with the guard and
     * the status its contract specifies.
     */
    public record AimCommand(AimInput value, long deadlineNanos) implements ClientMessage {}

    public record MineCommand(MineInput value, long deadlineNanos) implements ClientMessage {}

    public record HotbarSelectCommand(
            HotbarSelectInput value, long deadlineNanos) implements ClientMessage {}

    public record ScreenCommand(ScreenInput value, long deadlineNanos) implements ClientMessage {}

    public record GuiClickCommand(
            GuiClickInput value, long deadlineNanos) implements ClientMessage {}

    private record HeartbeatState(EnvelopeGate gate, Duration timeout, Set<String> capabilities) {
        private HeartbeatState {
            capabilities = Set.copyOf(capabilities);
        }
    }
}
