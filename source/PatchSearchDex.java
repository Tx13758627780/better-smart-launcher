import com.android.tools.smali.dexlib2.Opcode;
import com.android.tools.smali.dexlib2.dexbacked.DexBackedDexFile;
import com.android.tools.smali.dexlib2.iface.ClassDef;
import com.android.tools.smali.dexlib2.iface.Method;
import com.android.tools.smali.dexlib2.iface.instruction.FiveRegisterInstruction;
import com.android.tools.smali.dexlib2.iface.instruction.ReferenceInstruction;
import com.android.tools.smali.dexlib2.iface.reference.MethodReference;
import com.android.tools.smali.dexlib2.immutable.ImmutableClassDef;
import com.android.tools.smali.dexlib2.immutable.ImmutableMethod;
import com.android.tools.smali.dexlib2.immutable.reference.ImmutableMethodReference;
import com.android.tools.smali.dexlib2.builder.MutableMethodImplementation;
import com.android.tools.smali.dexlib2.builder.BuilderInstruction;
import com.android.tools.smali.dexlib2.builder.instruction.BuilderInstruction35c;
import com.android.tools.smali.dexlib2.writer.pool.DexPool;
import com.android.tools.smali.dexlib2.writer.io.FileDataStore;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.zip.ZipFile;

public final class PatchSearchDex {
    public static void main(String[] args) throws Exception {
        Set<String> targets = Set.of("Lqw2;", "Lf13;");
        Path target = Path.of(args[2]);
        Files.createDirectories(target);
        try (ZipFile apk = new ZipFile(args[0])) {
            DexBackedDexFile main = new DexBackedDexFile(null, apk.getInputStream(apk.getEntry("classes.dex")).readAllBytes());
            DexPool pool = new DexPool(main.getOpcodes());
            int changes = 0;
            for (ClassDef cls : main.getClasses()) {
                if (!targets.contains(cls.getType())) { pool.internClass(cls); continue; }
                List<Method> methods = new ArrayList<>();
                for (Method method : cls.getMethods()) {
                    if (!method.getName().equals("invokeSuspend")) { methods.add(method); continue; }
                    MutableMethodImplementation implementation = new MutableMethodImplementation(method.getImplementation());
                    for (int i = 0; i < implementation.getInstructions().size(); i++) {
                        BuilderInstruction instruction = implementation.getInstructions().get(i);
                        if (instruction.getOpcode() != Opcode.INVOKE_VIRTUAL || !(instruction instanceof ReferenceInstruction)) continue;
                        Object reference = ((ReferenceInstruction) instruction).getReference();
                        if (!(reference instanceof MethodReference)) continue;
                        MethodReference ref = (MethodReference) reference;
                        if (!ref.getDefiningClass().equals("Lpl7;") || !ref.getName().equals("g")) continue;
                        if (!ref.getReturnType().equals("I") || !ref.getParameterTypes().equals(Arrays.asList(
                                "Ljava/lang/String;", "Ljava/lang/String;", "Ljava/lang/String;")))
                            throw new IllegalStateException("Unexpected original matcher prototype");
                        FiveRegisterInstruction registers = (FiveRegisterInstruction) instruction;
                        if (registers.getRegisterCount() != 4) throw new IllegalStateException("Unexpected matcher registers");
                        MethodReference replacement = new ImmutableMethodReference("LLocalPinyin;", "score", Arrays.asList(
                                "Lpl7;", "Ljava/lang/String;", "Ljava/lang/String;", "Ljava/lang/String;"), "I");
                        implementation.replaceInstruction(i, new BuilderInstruction35c(Opcode.INVOKE_STATIC, 4,
                                registers.getRegisterC(), registers.getRegisterD(), registers.getRegisterE(),
                                registers.getRegisterF(), registers.getRegisterG(), replacement));
                        changes++;
                    }
                    methods.add(new ImmutableMethod(method.getDefiningClass(), method.getName(), method.getParameters(),
                            method.getReturnType(), method.getAccessFlags(), method.getAnnotations(), method.getHiddenApiRestrictions(), implementation));
                }
                pool.internClass(new ImmutableClassDef(cls.getType(), cls.getAccessFlags(), cls.getSuperclass(), cls.getInterfaces(),
                        cls.getSourceFile(), cls.getAnnotations(), cls.getFields(), methods));
            }
            if (changes != targets.size()) throw new IllegalStateException("Expected exactly two patches, found " + changes);
            FileDataStore firstOut = new FileDataStore(target.resolve("classes.dex").toFile());
            try { pool.writeTo(firstOut); } finally { firstOut.close(); }
            DexBackedDexFile secondary = new DexBackedDexFile(null, apk.getInputStream(apk.getEntry("classes2.dex")).readAllBytes());
            DexBackedDexFile helper = new DexBackedDexFile(null, Files.readAllBytes(Path.of(args[1])));
            DexPool secondPool = new DexPool(secondary.getOpcodes());
            Set<String> originals = new HashSet<>();
            for (ClassDef cls : secondary.getClasses()) { originals.add(cls.getType()); secondPool.internClass(cls); }
            Set<String> added = new HashSet<>();
            for (ClassDef cls : helper.getClasses()) {
                if (!cls.getType().startsWith("LLocalPinyin") || originals.contains(cls.getType()))
                    throw new IllegalStateException("Unexpected helper class: " + cls.getType());
                added.add(cls.getType());
                secondPool.internClass(cls);
            }
            if (!added.equals(Set.of("LLocalPinyin;", "LLocalPinyin$1;", "LLocalPinyin$NameForms;",
                    "LLocalPinyinData;", "LLocalPinyinData$Table;")))
                throw new IllegalStateException("Unexpected helper class set: " + added);
            FileDataStore secondOut = new FileDataStore(target.resolve("classes2.dex").toFile());
            try { secondPool.writeTo(secondOut); } finally { secondOut.close(); }
            System.out.println("Patched exactly " + changes + " local-app search calls in " + targets + "; added " + added);
        }
    }
}

